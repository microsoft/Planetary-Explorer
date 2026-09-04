export const CANADIAN_EXAMPLE_YEAR = 2026;
export const CANADIAN_OBSERVATION_RANGE = '2026-01-01/2026-08-26';

export interface ExampleQuery {
  query: string;
  description: string;
  dataset: string;
  pc_link?: string;
  rasterQuery?: string;
  screenshotQuery?: string;
}

export interface TerrainQuery {
  location: string;
  setupQuery: string;
  question: string;
  expectedTools: string[];
}

export interface MobilityQuery {
  location: string;
  setupQuery: string;
  question: string;
  analysisType: string;
}

export interface ExtremeWeatherQuery {
  location: string;
  setupQuery: string;
  question: string;
  variable: string;
}

export interface BuildingDamageQuery {
  location: string;
  setupQuery: string;
  question: string;
  analysisType: string;
}

export interface SiteAuditQuery {
  location: string;
  setupQuery: string;
  question: string;
  focus: string;
}

export interface ResilienceQuery {
  scenario: string;
  setupQuery: string;
  question: string;
  hazards: string;
}

export interface ForecastQuery {
  scenario: string;
  setupQuery: string;
  question: string;
  models: string;
}

export interface QueryCategory {
  category: string;
  icon?: string;
  examples: ExampleQuery[];
}

export const terrainQueries: TerrainQuery[] = [
  {
    location: 'Vancouver, British Columbia',
    setupQuery: 'Show Copernicus DEM elevation near Vancouver, Canada for 2026',
    question: 'For 2026, is this Metro Vancouver location suitable for a construction permit? Analyze slope, flood exposure, and flat areas.',
    expectedTools: ['get_slope_analysis', 'analyze_flood_risk', 'find_flat_areas'],
  },
  {
    location: 'Calgary, Alberta',
    setupQuery: 'Show Copernicus DEM elevation near Calgary, Alberta, Canada for 2026',
    question: 'Analyze 2026 terrain elevation, slope, aspect, and sun exposure near Calgary at 51.0447N, 114.0719W.',
    expectedTools: ['get_elevation_analysis', 'get_slope_analysis', 'get_aspect_analysis'],
  },
  {
    location: 'Halifax, Nova Scotia',
    setupQuery: 'Show Sentinel-2 imagery over Halifax, Canada from 2026-06-01 to 2026-08-26',
    question: 'Assess 2026 coastal flood exposure, environmental sensitivity, and permitting constraints for this Halifax site.',
    expectedTools: ['analyze_flood_risk', 'analyze_environmental_sensitivity'],
  },
];

export const mobilityQueries: MobilityQuery[] = [
  {
    location: 'Kananaskis, Alberta',
    setupQuery: 'Kananaskis, Alberta, Canada',
    question: 'Using 2026 conditions, classify vehicle traversability between these pins across five elevation layers and identify steep terrain barriers.',
    analysisType: 'Vehicle Route',
  },
  {
    location: 'North Shore Mountains, British Columbia',
    setupQuery: 'North Vancouver, British Columbia, Canada',
    question: 'For a 2026 search-and-rescue plan, identify flat helicopter landing zones between these pins and explain slope and vegetation constraints.',
    analysisType: 'SAR Landing Zone',
  },
  {
    location: 'Yukon River corridor, Yukon',
    setupQuery: 'Whitehorse, Yukon, Canada',
    question: 'Assess this 2026 emergency-supply route for water crossings, wildfire exposure, steep slopes, and ground-vehicle feasibility.',
    analysisType: 'Emergency Supply Corridor',
  },
];

export const siteAuditQueries: SiteAuditQuery[] = [
  {
    location: 'Calgary region, Alberta - Data centre',
    setupQuery: 'Calgary, Alberta, Canada',
    question: 'For 2026, score our candidate data-centre sites near Calgary for power, water, competition, wildfire, flood, and heat exposure.',
    focus: 'Power + Water + Hazard',
  },
  {
    location: 'Montreal region, Quebec - Industrial parcels',
    setupQuery: 'Montreal, Quebec, Canada',
    question: 'Which 2026 candidate parcels near Montreal clear slope, flood, heat, and grid-proximity thresholds?',
    focus: 'Parcel Screening + Grid',
  },
  {
    location: 'Edmonton region, Alberta - Grid expansion',
    setupQuery: 'Edmonton, Alberta, Canada',
    question: 'Rank the top three 2026 sites near Edmonton with permitting precedent and grid proximity weighted highest.',
    focus: 'Permitting + Grid Proximity',
  },
];

export const resilienceQueries: ResilienceQuery[] = [
  {
    scenario: 'Seven-day Canadian facility outlook',
    setupQuery: 'Canada',
    question: 'Over the next seven days, which Canadian facilities are most at risk and what is the supply-chain blast radius?',
    hazards: 'Heat + Wildfire + Flood',
  },
  {
    scenario: 'Vancouver distribution disruption',
    setupQuery: 'Vancouver, British Columbia, Canada',
    question: 'If our Vancouver distribution centre goes offline for 48 hours in 2026, which downstream Canadian facilities are exposed?',
    hazards: 'Supply Chain + Lead Time',
  },
  {
    scenario: 'Western Canada weekly review',
    setupQuery: 'Western Canada',
    question: 'Show 2026 heat and wildfire risk for all Western Canada facilities this week, ranked by severity with a response playbook.',
    hazards: 'Heat + Wildfire + BCP',
  },
];

export const forecastQueries: ForecastQuery[] = [
  {
    scenario: 'Great Lakes five-day ensemble',
    setupQuery: 'Lake Ontario, Canada',
    question: 'Give me a 120-hour (five-day) forecast over Lake Ontario using every available model and summarize ensemble spread.',
    models: 'Every configured provider (120h)',
  },
  {
    scenario: 'Prairie temperature and wind',
    setupQuery: 'Saskatchewan, Canada',
    question: 'Forecast 2m temperature and 10m wind across southern Saskatchewan for the next 72 hours.',
    models: 'Every configured provider (72h)',
  },
  {
    scenario: 'Atlantic Canada precipitation comparison',
    setupQuery: 'Nova Scotia, Canada',
    question: 'Compare Aurora and Earth-2 FCN precipitation over Nova Scotia for the next 24 hours and explain model disagreement.',
    models: 'Aurora + Earth-2 FCN',
  },
];

export const extremeWeatherQueries: ExtremeWeatherQuery[] = [
  {
    location: 'Vancouver, British Columbia',
    setupQuery: 'Vancouver, British Columbia, Canada',
    question: 'What are the projected annual precipitation and peak daily rainfall values for Vancouver in 2026?',
    variable: 'pr (Coastal Flood Risk)',
  },
  {
    location: 'Toronto, Ontario',
    setupQuery: 'Toronto, Ontario, Canada',
    question: 'Show monthly projected precipitation for Toronto in 2026 and identify the wettest month.',
    variable: 'pr (Urban Flooding)',
  },
  {
    location: 'Montreal, Quebec',
    setupQuery: 'Montreal, Quebec, Canada',
    question: 'What are the projected temperature and precipitation trends for Montreal during 2026 under SSP245 and SSP585?',
    variable: 'tasmax + pr (Scenario Comparison)',
  },
];

export const buildingDamageQueries: BuildingDamageQuery[] = [
  {
    location: 'Jasper, Alberta',
    setupQuery: 'Show my MPC Pro aerial imagery over Jasper, Alberta from 2026-01-01 to 2026-08-26',
    question: 'Using the 2026 before-and-after tenant imagery, assess potential building damage and distinguish destroyed, major-damage, and unaffected structures.',
    analysisType: 'Wildfire Damage (MPC Pro)',
  },
  {
    location: 'Lytton, British Columbia',
    setupQuery: 'Show my MPC Pro aerial imagery over Lytton, British Columbia, Canada from 2026-01-01 to 2026-08-26',
    question: 'Using the 2026 before-and-after tenant imagery, assess structural damage and identify blocks requiring field verification.',
    analysisType: 'Building Damage (MPC Pro)',
  },
];

export const exampleQueries: QueryCategory[] = [
  {
    category: 'Optical Imagery',
    examples: [
      {
        query: 'Show Sentinel-2 imagery over Toronto, Canada from 2026-06-01 to 2026-08-26',
        description: '10m surface-reflectance imagery for the Greater Toronto Area',
        dataset: 'Sentinel-2 L2A',
        rasterQuery: 'Sample the 2026 red and near-infrared reflectance values at this pin.',
        screenshotQuery: 'Explain the colours in this 2026 Toronto image and identify visible land-cover types.',
      },
      {
        query: 'Show HLS S30 imagery at Calgary, Canada, latitude 51.0300, longitude -114.0800, from 2026-05-01 to 2026-08-26',
        description: '30m harmonized Sentinel-2 imagery at a verified Calgary pixel',
        dataset: 'HLS S30',
        rasterQuery: 'What is the 2026 NDVI value at this Calgary pin?',
        screenshotQuery: 'Describe urban growth and vegetation patterns visible around Calgary in 2026.',
      },
      {
        query: 'Show Landsat imagery over Halifax, Canada from 2026-01-01 to 2026-08-26',
        description: 'Landsat Collection 2 surface reflectance over coastal Nova Scotia',
        dataset: 'Landsat C2 L2',
        rasterQuery: 'Sample the 2026 coastal surface-reflectance bands at this location.',
        screenshotQuery: 'Identify water, urban, forest, and shoreline features in this 2026 Halifax image.',
      },
    ],
  },
  {
    category: 'Fire and Vegetation',
    examples: [
      {
        query: 'Show MODIS thermal anomalies at latitude 54.5000, longitude -115.0000 in Alberta from 2026-05-01 to 2026-08-26',
        description: 'Daily 1km active-fire observations at a verified Alberta pixel',
        dataset: 'MODIS 14A1',
        rasterQuery: 'What are the 2026 MaxFRP and FireMask values at this Alberta pixel?',
        screenshotQuery: 'State the colours actually visible in this 2026 MODIS thermal-anomaly image and whether any clusters are visible, then explain only those visible colours at this Alberta location.',
      },
      {
        query: 'Show MODIS 13Q1 vegetation indices over cropland south of Regina, Saskatchewan, Canada, latitude 50.3500, longitude -104.6000, from 2026-04-01 to 2026-08-26',
        description: '250m NDVI and EVI composites at verified Regina cropland',
        dataset: 'MODIS 13Q1',
        rasterQuery: 'Sample the 2026 NDVI and EVI values at this Regina cropland pin.',
        screenshotQuery: 'Explain the vegetation colours and identify lower-vigour areas near Regina in 2026.',
      },
      {
        query: 'Show collection modis-17A2H-061 gross primary productivity at latitude 54.1500, longitude -126.5500 in British Columbia from 2026-05-01 to 2026-08-26',
        description: '8-day vegetation productivity at a verified interior BC pixel',
        dataset: 'MODIS 17A2H',
        rasterQuery: 'What is the 2026 gross primary productivity value at this interior BC pin?',
        screenshotQuery: 'State the colour actually visible in this 2026 GPP image and whether it varies, then explain only that visible productivity colour at this interior British Columbia location.',
      },
    ],
  },
  {
    category: 'Water, Snow, and Ice',
    examples: [
      {
        query: 'Show MODIS 10A1 daily snow cover at Quebec City, Canada, latitude 46.8139, longitude -71.2080, from 2025-02-01 to 2025-02-28',
        description: '500m archived daily snow cover at a verified Quebec City pixel',
        dataset: 'MODIS 10A1',
        rasterQuery: 'Sample the February 2025 NDSI value at this Quebec City pin.',
        screenshotQuery: 'State the colours actually visible in this February 2025 MODIS snow-cover image and whether they vary, then explain only those visible colours around Quebec City.',
      },
      {
        query: 'Show Sentinel-2 imagery along the Mackenzie River near Norman Wells, Canada from 2026-05-01 to 2026-06-30',
        description: '10m spring river and ice observations near Norman Wells',
        dataset: 'Sentinel-2 L2A',
        rasterQuery: 'Sample 2026 Sentinel-2 green, near-infrared, and short-wave infrared reflectance at this Mackenzie River pin.',
        screenshotQuery: 'Identify open water, ice, snow, and land in this 2026 image.',
      },
      {
        query: 'Show Landsat Collection 2 Level-2 imagery along the Hudson Bay coast at Churchill, Manitoba, Canada, latitude 58.7684, longitude -94.1650, from 2026-06-01 to 2026-08-26',
        description: '30m summer coastal observations at a verified Churchill pixel',
        dataset: 'Landsat C2 L2',
        rasterQuery: 'Sample the 2026 green, near-infrared, and short-wave infrared bands at this Churchill pin.',
        screenshotQuery: 'Explain the natural-colour rendering and identify water, cloud, tundra, and coast near Churchill.',
      },
    ],
  },
  {
    category: 'Terrain and Radar',
    examples: [
      {
        query: 'Show Copernicus DEM terrain around Banff, Canada for 2026 analysis',
        description: '30m elevation used for current-year terrain analysis',
        dataset: 'COP-DEM GLO-30',
        rasterQuery: 'Sample the exact Copernicus DEM pixel elevation in metres at this Banff pin; do not return an area mean or range.',
        screenshotQuery: 'Explain the elevation colours and identify valleys, slopes, and peaks.',
      },
      {
        query: 'Show Sentinel-1 RTC radar imagery over Vancouver, Canada from 2026-01-01 to 2026-08-26',
        description: '10m terrain-corrected radar backscatter for Metro Vancouver',
        dataset: 'Sentinel-1 RTC',
        rasterQuery: 'What are the 2026 VV and VH backscatter values in dB?',
        screenshotQuery: 'Explain the radar colours and distinguish water, vegetation, and built-up areas.',
      },
      {
        query: 'Show Sentinel-1 RTC radar imagery over the Red River, Manitoba from 2026-03-01 to 2026-05-31',
        description: 'All-weather radar observations for spring flood monitoring',
        dataset: 'Sentinel-1 RTC',
        rasterQuery: 'Sample the 2026 radar backscatter at this Red River pin.',
        screenshotQuery: 'Explain the radar colour composite and identify possible inundation.',
      },
    ],
  },
];

export const allCanadianExampleText = [
  ...terrainQueries.flatMap(({ setupQuery, question }) => [setupQuery, question]),
  ...mobilityQueries.flatMap(({ setupQuery, question }) => [setupQuery, question]),
  ...siteAuditQueries.flatMap(({ setupQuery, question }) => [setupQuery, question]),
  ...resilienceQueries.flatMap(({ setupQuery, question }) => [setupQuery, question]),
  ...forecastQueries.flatMap(({ setupQuery, question }) => [setupQuery, question]),
  ...extremeWeatherQueries.flatMap(({ setupQuery, question }) => [setupQuery, question]),
  ...buildingDamageQueries.flatMap(({ setupQuery, question }) => [setupQuery, question]),
  ...exampleQueries.flatMap(({ examples }) => examples.flatMap(({ query, rasterQuery, screenshotQuery }) => [query, rasterQuery, screenshotQuery].filter(Boolean) as string[])),
];