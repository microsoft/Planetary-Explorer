import { describe, expect, it } from 'vitest';

import {
  buildingDamageQueries,
  exampleQueries,
  extremeWeatherQueries,
  forecastQueries,
  mobilityQueries,
  resilienceQueries,
  siteAuditQueries,
  terrainQueries,
} from '../canadianExamples';

const canadianPlace = /Canada|Alberta|British Columbia|Manitoba|Nova Scotia|Ontario|Quebec|Saskatchewan|Yukon/i;
const legacyPlace = /Afghanistan|Arizona|Australia|Bangladesh|California|Colorado|Ecuador|Florida|Louisiana|Mexico|Mozambique|Nepal|Sudan|Texas|Thailand|Ukraine|United Kingdom|Virginia|Washington, DC/i;

const workflowExamples = [
  ...terrainQueries.map((example) => ({ context: `${example.location} ${example.setupQuery}`, prompt: example.question })),
  ...mobilityQueries.map((example) => ({ context: `${example.location} ${example.setupQuery}`, prompt: example.question })),
  ...siteAuditQueries.map((example) => ({ context: `${example.location} ${example.setupQuery}`, prompt: example.question })),
  ...resilienceQueries.map((example) => ({ context: `${example.scenario} ${example.setupQuery}`, prompt: example.question })),
  ...forecastQueries.map((example) => ({ context: `${example.scenario} ${example.setupQuery}`, prompt: example.question })),
  ...extremeWeatherQueries.map((example) => ({ context: `${example.location} ${example.setupQuery}`, prompt: example.question })),
  ...buildingDamageQueries.map((example) => ({ context: `${example.location} ${example.setupQuery}`, prompt: example.question })),
  ...exampleQueries.flatMap((category) => category.examples.map((example) => ({ context: example.query, prompt: example.query }))),
];

describe('Canadian starter examples', () => {
  it('keeps every primary workflow prompt time-bounded', () => {
    expect(workflowExamples.every(({ prompt }) => (
      /202[56]|next \d+|next (?:one|two|three|four|five|six|seven|\w+)|(?:\d+|one|two|three|four|five|six|seven)[-\s]day|this week/i.test(prompt)
    ))).toBe(true);
  });

  it('does not retain stale fixed-date forecast or resilience prompts', () => {
    const allText = workflowExamples.map(({ prompt }) => prompt).join('\n');

    expect(allText).not.toMatch(/August 2[6-9](?:-31)?, 2026/i);
  });

  it('keeps every workflow example in a Canadian context', () => {
    expect(workflowExamples.every(({ context }) => canadianPlace.test(context))).toBe(true);
  });

  it('does not reintroduce legacy international example locations', () => {
    const allText = workflowExamples.map(({ context, prompt }) => `${context} ${prompt}`).join('\n');

    expect(allText).not.toMatch(legacyPlace);
  });

  it('keeps the MODIS fire screenshot prompt grounded in visible pixels', () => {
    const fireExample = exampleQueries
      .flatMap((category) => category.examples)
      .find((example) => example.dataset === 'MODIS 14A1');

    expect(fireExample?.screenshotQuery).toContain('colours actually visible');
    expect(fireExample?.screenshotQuery).toContain('whether any clusters are visible');
    expect(fireExample?.screenshotQuery).toContain('only those visible colours');
  });
});