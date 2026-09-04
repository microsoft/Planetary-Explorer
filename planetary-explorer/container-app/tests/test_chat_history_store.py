"""Tests for owner-isolated chat history persistence."""

import copy

import pytest

import chat_history_store
from chat_history_store import (
    BlobArtifactStore,
    ChatHistoryError,
    ChatHistoryConflictError,
    ChatHistoryValidationError,
    CosmosChatHistoryRepository,
    InMemoryArtifactStore,
    InMemoryChatHistoryRepository,
    normalize_session_document,
    public_session_document,
)


class _FakeBlob:
    def __init__(self) -> None:
        self.upload: dict | None = None

    async def upload_blob(self, content: bytes, **kwargs) -> None:
        self.upload = {"content": content, **kwargs}


class _FakeBlobContainer:
    def __init__(self) -> None:
        self.blob = _FakeBlob()

    def get_blob_client(self, _blob_name: str) -> _FakeBlob:
        return self.blob


class _CosmosStatusError(Exception):
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _ConflictingCosmosContainer:
    def __init__(self) -> None:
        self.document = normalize_session_document(
            "tenant:user-1",
            "web-session-1",
            {
                "expectedRevision": 0,
                "mutationId": "cosmos-initial-save",
                "messages": [{"role": "user", "content": "old"}],
            },
        )
        self.document["_etag"] = "etag-1"
        self.replace_calls = 0

    async def read_item(self, *, item: str, partition_key: str) -> dict:
        assert item == "web-session-1"
        assert partition_key == "tenant:user-1"
        return copy.deepcopy(self.document)

    async def replace_item(self, *, item: str, body: dict, **_kwargs) -> dict:
        self.replace_calls += 1
        if self.replace_calls == 1:
            self.document["attachments"] = [{"id": "concurrent-file"}]
            self.document["_etag"] = "etag-2"
            raise _CosmosStatusError(412)
        self.document = copy.deepcopy(body)
        self.document["_etag"] = "etag-3"
        return copy.deepcopy(self.document)


@pytest.mark.parametrize(
    "messages",
    [
        {"role": "user", "content": "not an array"},
        [{"role": "system", "content": "unsupported role"}],
    ],
)
def test_given_malformed_messages_when_normalized_then_snapshot_is_rejected(
    messages,
) -> None:
    # Arrange
    payload = {
        "expectedRevision": 0,
        "mutationId": "invalid-messages-save",
        "messages": messages,
    }

    # Act and assert
    with pytest.raises(ChatHistoryValidationError):
        normalize_session_document("tenant:user-1", "web-session-1", payload)


def test_given_more_than_message_limit_when_normalized_then_snapshot_is_rejected() -> None:
    # Arrange
    payload = {
        "expectedRevision": 0,
        "mutationId": "too-many-messages-save",
        "messages": [
            {"role": "user", "content": f"message {index}"}
            for index in range(chat_history_store.MAX_MESSAGES + 1)
        ],
    }

    # Act and assert
    with pytest.raises(ChatHistoryValidationError, match="200-message limit"):
        normalize_session_document("tenant:user-1", "web-session-1", payload)


@pytest.mark.parametrize("expected_revision", [True, "1"])
def test_given_non_integer_revision_when_normalized_then_snapshot_is_rejected(
    expected_revision,
) -> None:
    # Arrange
    payload = {
        "expectedRevision": expected_revision,
        "mutationId": "invalid-revision-save",
        "messages": [{"role": "user", "content": "Test"}],
    }

    # Act & Assert
    with pytest.raises(ChatHistoryValidationError, match="non-negative integer"):
        normalize_session_document("tenant:user-1", "web-session-1", payload)


def test_given_chat_legend_when_normalized_then_colour_explanation_is_preserved() -> None:
    # Arrange
    legend = {
        "title": "Facility risk severity",
        "items": [
            {"color": "#22c55e", "label": "Low"},
            {"color": "#dc2626", "label": "Severe"},
        ],
    }
    payload = {
        "expectedRevision": 0,
        "mutationId": "legend-save",
        "messages": [
            {"role": "assistant", "content": "Risk results", "legend": legend}
        ],
    }

    # Act
    document = normalize_session_document("tenant:user-1", "web-session-1", payload)

    # Assert
    assert document["messages"][0]["legend"] == legend


@pytest.mark.asyncio
async def test_given_same_session_id_when_owners_differ_then_history_is_isolated() -> None:
    # Arrange
    repository = InMemoryChatHistoryRepository()

    # Act
    await repository.upsert_session(
        "tenant:user-1",
        "web-session-1",
        {
            "expectedRevision": 0,
            "mutationId": "owner-one-save",
            "messages": [{"role": "user", "content": "first"}],
        },
    )
    await repository.upsert_session(
        "tenant:user-2",
        "web-session-1",
        {
            "expectedRevision": 0,
            "mutationId": "owner-two-save",
            "messages": [{"role": "user", "content": "second"}],
        },
    )

    # Assert
    first = await repository.get_session("tenant:user-1", "web-session-1")
    second = await repository.get_session("tenant:user-2", "web-session-1")
    assert first["messages"][0]["content"] == "first"
    assert second["messages"][0]["content"] == "second"


def test_given_sensitive_context_when_normalized_then_secrets_and_large_data_are_removed() -> None:
    # Arrange
    signed_url = "https://example.blob.core.windows.net/file.tif?sv=1&sig=secret"
    payload = {
        "expectedRevision": 0,
        "mutationId": "sanitization-save",
        "messages": [
            {
                "role": "assistant",
                "content": f"Download {signed_url}",
                "toolTrace": [{"args": {
                    "accessToken": "secret",
                    "authorization": "Bearer abc.def.ghi",
                    "artifact_uri": signed_url,
                }}],
            }
        ],
        "context": {
            "selectedModel": "gpt-5",
            "map": {
                "imagery_base64": "a" * 1000,
                "stac_items": [{"assets": {"data": {"href": signed_url}}}],
                "bounds": {"north": 1},
            },
        },
    }

    # Act
    document = normalize_session_document("tenant:user-1", "web-session-1", payload)
    public = public_session_document(document)

    # Assert
    assert public["messages"][0]["content"].endswith("?<redacted>")
    assert "accessToken" not in public["messages"][0]["toolTrace"][0]["args"]
    assert "authorization" not in public["messages"][0]["toolTrace"][0]["args"]
    assert public["context"]["map"] == {"bounds": {"north": 1}}
    assert "ownerId" not in public


def test_given_scene_references_when_normalized_then_safe_provenance_is_preserved() -> None:
    # Arrange
    payload = {
        "expectedRevision": 0,
        "mutationId": "scene-provenance-save",
        "messages": [{"role": "user", "content": "Restore this map"}],
        "context": {
            "map": {
                "scene_refs": [
                    {
                        "id": "private-scene",
                        "collection": "private-imagery",
                        "stac_mode": "pro",
                        "bbox": [-123, 47, -122, 48],
                        "datetime": "2026-06-15T00:00:00Z",
                        "assets": {
                            "data": {
                                "href": "https://example.test/data.tif?sig=secret"
                            }
                        },
                    }
                ]
            }
        },
    }

    # Act
    document = normalize_session_document("tenant:user-1", "web-session-1", payload)

    # Assert
    scene = document["context"]["map"]["scene_refs"][0]
    assert scene == {
        "id": "private-scene",
        "collection": "private-imagery",
        "stac_mode": "pro",
        "bbox": [-123, 47, -122, 48],
        "datetime": "2026-06-15T00:00:00Z",
    }


def test_given_credential_urls_when_normalized_then_userinfo_and_secret_queries_are_redacted() -> None:
    # Arrange
    payload = {
        "expectedRevision": 0,
        "mutationId": "credential-url-save",
        "messages": [
            {
                "role": "user",
                "content": (
                    "Use https://alice:password@example.test/private and "
                    "https://example.test/token?client_secret=secret-value and "
                    "https://example.test/api?Ocp-Apim-Subscription-Key=api-secret"
                ),
            }
        ],
    }

    # Act
    document = normalize_session_document("tenant:user-1", "web-session-1", payload)
    content = document["messages"][0]["content"]

    # Assert
    assert "alice" not in content
    assert "password" not in content
    assert "secret-value" not in content
    assert "api-secret" not in content
    assert "<redacted-url>" in content
    assert content.count("?<redacted>") == 2


def test_given_connection_secrets_when_normalized_then_fields_and_assignments_are_redacted() -> None:
    # Arrange
    payload = {
        "expectedRevision": 0,
        "mutationId": "connection-secret-save",
        "messages": [
            {
                "role": "assistant",
                "content": (
                    "DefaultEndpointsProtocol=https;AccountName=demo;"
                    "AccountKey=account-secret;EndpointSuffix=core.windows.net "
                    "Endpoint=sb://demo.servicebus.windows.net/;"
                    "SharedAccessKeyName=Root;SharedAccessKey=bus-secret "
                    "AZURE_STORAGE_ACCOUNT_KEY=env-secret "
                    "client_secret: oauth-secret api-key=api-secret "
                    "subscription_key: sub-secret SAS=sas-secret "
                    "sv=2026-01-01&sp=r&sig=raw-sas-secret "
                    "client_secret=\"quoted-secret\" "
                    "Authorization: Bearer eyJhbGciOi.test-token/signature=="
                ),
                "toolTrace": [
                    {
                        "args": {
                            "connectionString": "AccountKey=structured-secret",
                            "accountKey": "account-field-secret",
                            "sharedAccessKey": "shared-field-secret",
                            "databasePassword": "database-secret",
                            "azureOpenAiApiKey": "openai-secret",
                            "safe": "retained",
                        }
                    }
                ],
            }
        ],
    }

    # Act
    document = normalize_session_document("tenant:user-1", "web-session-1", payload)
    message = document["messages"][0]
    args = message["toolTrace"][0]["args"]

    # Assert
    assert "connectionString" not in args
    assert "accountKey" not in args
    assert "sharedAccessKey" not in args
    assert "databasePassword" not in args
    assert "azureOpenAiApiKey" not in args
    assert args["safe"] == "retained"
    assert "account-secret" not in message["content"]
    assert "bus-secret" not in message["content"]
    assert "env-secret" not in message["content"]
    assert "oauth-secret" not in message["content"]
    assert "api-secret" not in message["content"]
    assert "sub-secret" not in message["content"]
    assert "sas-secret" not in message["content"]
    assert "raw-sas-secret" not in message["content"]
    assert "quoted-secret" not in message["content"]
    assert "test-token" not in message["content"]
    assert "AccountKey=<redacted>" in message["content"]
    assert "SharedAccessKey=<redacted>" in message["content"]
    assert "AZURE_STORAGE_ACCOUNT_KEY=<redacted>" in message["content"]
    assert "client_secret:<redacted>" in message["content"]
    assert "api-key=<redacted>" in message["content"]
    assert "subscription_key:<redacted>" in message["content"]
    assert "SAS=<redacted>" in message["content"]
    assert "sig=<redacted>" in message["content"]
    assert "Authorization:<redacted>" in message["content"]


@pytest.mark.asyncio
async def test_given_data_file_when_uploaded_then_manifest_and_bytes_round_trip() -> None:
    # Arrange
    store = InMemoryArtifactStore()
    content = b"latitude,longitude\n47.6,-122.3\n"

    # Act
    attachment = await store.upload(
        "tenant:user-1",
        "web-session-1",
        "test-data.csv",
        "text/csv",
        content,
    )
    downloaded = await store.download(attachment)

    # Assert
    assert attachment["name"] == "test-data.csv"
    assert attachment["size"] == len(content)
    assert downloaded == content


@pytest.mark.asyncio
async def test_given_blob_upload_when_content_type_supplied_then_uses_content_settings() -> None:
    # Arrange
    container = _FakeBlobContainer()
    store = BlobArtifactStore(
        "https://storage.example",
        "chat-artifacts",
        container_client=container,
    )

    # Act
    await store.upload(
        "tenant:user-1",
        "web-session-1",
        "coordinates.csv",
        "text/csv",
        b"lat,lng\n",
    )

    # Assert
    assert container.blob.upload is not None
    assert container.blob.upload["content_settings"].content_type == "text/csv"


@pytest.mark.asyncio
async def test_given_cosmos_etag_conflict_when_saving_then_retries_without_losing_attachments() -> None:
    # Arrange
    container = _ConflictingCosmosContainer()
    repository = CosmosChatHistoryRepository(
        "https://cosmos.example",
        "planetary-explorer",
        "chat-history",
        container_client=container,
    )

    # Act
    saved = await repository.upsert_session(
        "tenant:user-1",
        "web-session-1",
        {
            "expectedRevision": 1,
            "mutationId": "cosmos-updated-save",
            "messages": [{"role": "user", "content": "new"}],
        },
    )

    # Assert
    assert container.replace_calls == 2
    assert saved["messages"][0]["content"] == "new"
    assert saved["attachments"] == [{"id": "concurrent-file"}]


def test_given_disabled_modes_with_endpoints_when_resolved_then_stores_remain_disabled(
    monkeypatch,
) -> None:
    # Arrange
    monkeypatch.setattr(chat_history_store, "_history_repository", None)
    monkeypatch.setattr(chat_history_store, "_artifact_store", None)
    monkeypatch.setenv("CHAT_HISTORY_STORE", "disabled")
    monkeypatch.setenv("COSMOS_CHAT_ENDPOINT", "https://cosmos.example")
    monkeypatch.setenv("CHAT_ARTIFACT_STORE", "disabled")
    monkeypatch.setenv("CHAT_ARTIFACT_BLOB_ENDPOINT", "https://blob.example")

    # Act & Assert
    with pytest.raises(ChatHistoryError, match="history is disabled"):
        chat_history_store.get_chat_history_repository()
    with pytest.raises(ChatHistoryError, match="artifacts are disabled"):
        chat_history_store.get_artifact_store()


def test_given_memory_modes_with_cloud_endpoints_when_resolved_then_memory_remains_authoritative(
    monkeypatch,
) -> None:
    # Arrange
    monkeypatch.setattr(chat_history_store, "_history_repository", None)
    monkeypatch.setattr(chat_history_store, "_artifact_store", None)
    monkeypatch.setenv("CHAT_HISTORY_STORE", "memory")
    monkeypatch.setenv("COSMOS_CHAT_ENDPOINT", "https://cosmos.example")
    monkeypatch.setenv("CHAT_ARTIFACT_STORE", "memory")
    monkeypatch.setenv("CHAT_ARTIFACT_BLOB_ENDPOINT", "https://blob.example")

    # Act
    repository = chat_history_store.get_chat_history_repository()
    artifact_store = chat_history_store.get_artifact_store()

    # Assert
    assert isinstance(repository, InMemoryChatHistoryRepository)
    assert isinstance(artifact_store, InMemoryArtifactStore)


def test_given_unknown_store_modes_when_resolved_then_configuration_fails_closed(
    monkeypatch,
) -> None:
    # Arrange
    monkeypatch.setattr(chat_history_store, "_history_repository", None)
    monkeypatch.setattr(chat_history_store, "_artifact_store", None)
    monkeypatch.setenv("CHAT_HISTORY_STORE", "typo")
    monkeypatch.setenv("CHAT_ARTIFACT_STORE", "typo")

    # Act & Assert
    with pytest.raises(ChatHistoryError, match="must be cosmos, memory, or disabled"):
        chat_history_store.get_chat_history_repository()
    with pytest.raises(ChatHistoryError, match="must be blob, memory, or disabled"):
        chat_history_store.get_artifact_store()


@pytest.mark.asyncio
async def test_given_session_deletion_tombstone_when_write_arrives_then_write_is_rejected() -> None:
    # Arrange
    repository = InMemoryChatHistoryRepository()
    document = await repository.upsert_session(
        "tenant:user-1",
        "web-session-1",
        {
            "expectedRevision": 0,
            "mutationId": "tombstone-initial-save",
            "messages": [{"role": "user", "content": "original"}],
        },
    )
    deleting = await repository.begin_delete(
        "tenant:user-1",
        "web-session-1",
        document["_etag"],
    )

    # Act & Assert
    with pytest.raises(ChatHistoryConflictError, match="being deleted"):
        await repository.upsert_session(
            "tenant:user-1",
            "web-session-1",
            {
                "expectedRevision": 1,
                "mutationId": "tombstone-late-save",
                "messages": [{"role": "user", "content": "late write"}],
            },
        )
    await repository.delete_session(
        "tenant:user-1",
        "web-session-1",
        deleting["_etag"],
    )