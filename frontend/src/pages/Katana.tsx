import { useState, useEffect, useMemo } from 'react';
import { 
  Cpu,
  Wrench,
  ArrowRightLeft,
  Plus,
  Save,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  ShieldCheck,
  Zap,
  Trash2,
  RefreshCw,
  Link2,
  X,
  Search,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Puzzle,
  Globe,
  SlidersHorizontal,
  Star,
  StarOff,
  Shield,
  GitBranch,
  Download,
  Layers,
  Folder,
  MessageCircle,
  Send,
  Wifi,
  WifiOff,
  Check,
  Eye,
  EyeOff,
  Edit2,
  Mail,
  Cloud,
  Monitor,
  FileSpreadsheet,
  Loader2,
  Power,
  FolderOpen,
  FileText,
  AppWindow,
  Crosshair,
  Users,
} from "lucide-react";
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { cn } from '../lib/utils';
import { setSafeObjectPath } from '../lib/safeObjectPath';
import { useTranslation } from '../i18n';
import { MicrosoftTeamsAdapterTab } from './katana/MicrosoftTeamsAdapterTab';
import { Mado } from './Mado';
import { Ronin } from './Ronin';
import { IdeModeTab } from './katana/IdeModeTab';
import ModelRoutingPanel from './katana/ModelRoutingPanel';
import ActiveSkillsPanel from './katana/ActiveSkillsPanel';
import { SkillOptTab } from './katana/SkillOptTab';
import { FileFormatsPanel } from './katana/FileFormatsPanel';
import { TeamMembersPanel } from './katana/TeamMembersPanel';

type TabType = 'providers' | 'tools' | 'files' | 'routing' | 'skills' | 'team' | 'telegram' | 'teams' | 'mail_calendar' | 'office' | 'ide' | 'mado' | 'ronin' | 'skillopt';
type RegisterMode = 'quick' | 'manual';

// ── Documentation links for cloud providers ─────────────────────
const PROVIDER_DOCS: Record<string, { label: string; url: string }> = {
  google:     { label: 'Gemini Model Reference',   url: 'https://ai.google.dev/gemini-api/docs/models' },
  openai:     { label: 'OpenAI Model Reference',    url: 'https://platform.openai.com/docs/models' },
  anthropic:  { label: 'Claude Model Overview',     url: 'https://platform.claude.com/docs/en/about-claude/models/overview' },
  openrouter: { label: 'OpenRouter Model Catalog',  url: 'https://openrouter.ai/models' },
};

const PROVIDER_BASE_URLS: Record<string, string> = {
  openai:     'https://api.openai.com/v1',
  google:     'https://generativelanguage.googleapis.com/v1beta/openai',
  anthropic:  'https://api.anthropic.com/v1',
  openrouter: 'https://openrouter.ai/api/v1',
  ollama:     'http://127.0.0.1:11434',
  lmstudio:   'http://localhost:1234/v1',
  local:      'http://localhost:1234/v1',
  custom:     '',
};

const PROVIDER_MODEL_PRESETS: Record<string, string[]> = {
  openai: ['gpt-5'],
  anthropic: ['claude-sonnet-5'],
  google: ['gemini-3.5-flash'],
  openrouter: ['z-ai/glm-5.2', 'google/gemini-3.5-flash', 'anthropic/claude-sonnet-5'],
  ollama: ['llama3.2', 'qwen2.5-coder', 'deepseek-r1:8b', 'mistral'],
};

const LOCAL_PROVIDERS = ['ollama', 'lmstudio', 'local'];
const isLocalProvider = (type: string) => LOCAL_PROVIDERS.includes(type);

// ── Ollama live search result type ───────────────────────────────
interface OllamaSearchResult {
  id: string; name: string; description: string;
  sizes: string[]; capabilities: string[];
  pulls: string; tag_count: number; updated: string;
}

// ── Connector enums (mirror backend) ────────────────────────────
const CONNECTOR_TYPES = ['api', 'tool', 'mcp', 'filesystem', 'database', 'queue', 'custom'] as const;
const AUTH_TYPES      = ['api_key', 'oauth', 'token', 'custom', 'none'] as const;
const RISK_LEVELS     = ['low', 'medium', 'high', 'critical'] as const;

type ConnectorTypeVal = typeof CONNECTOR_TYPES[number];
type AuthTypeVal      = typeof AUTH_TYPES[number];
type RiskLevelVal     = typeof RISK_LEVELS[number];

// ── Curated public API catalog ───────────────────────────────────
interface PublicApi {
  name: string;
  description: string;
  base_url: string;
  auth_type: AuthTypeVal;
  connector_type: ConnectorTypeVal;
  risk_level: RiskLevelVal;
}

const PUBLIC_APIS: PublicApi[] = [
  // ── Weather ────────────────────────────────────────────────
  { name: 'OpenWeatherMap',         description: 'Current weather, 5-day forecasts, and 40+ year historical data for any location.', base_url: 'https://api.openweathermap.org/data/2.5', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'WeatherAPI',             description: 'Real-time, forecast, and historical weather covering astronomy, air quality and alerts.', base_url: 'https://api.weatherapi.com/v1', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'Open-Meteo',             description: 'Free, open-source weather API with hourly forecasts and no API key required.', base_url: 'https://api.open-meteo.com/v1', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'Tomorrow.io',            description: 'Hyper-local weather intelligence with AI-powered forecasting.', base_url: 'https://api.tomorrow.io/v4', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'NOAA NGDC',              description: 'Natural hazards data including earthquakes, tsunamis, and volcanic eruptions.', base_url: 'https://www.ngdc.noaa.gov/hazel/hazard-service/api/v1', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'Air Quality Index',      description: 'Real-time air quality data including AQI and pollutant concentrations for worldwide locations.', base_url: 'https://api.api-ninjas.com/v1/airquality', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'Storm Glass',            description: 'Marine weather, solar and wind energy data, and tide forecasts from premium sources.', base_url: 'https://api.stormglass.io/v2', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'Météo-France',           description: 'Official French meteorological service API — forecasts, radar, and climatology.', base_url: 'https://public-api.meteofrance.fr/public', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  // ── Science & Math ─────────────────────────────────────────
  { name: 'NASA APOD',              description: 'Astronomy Picture of the Day with title, explanation, and image URL.', base_url: 'https://api.nasa.gov/planetary/apod', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'NASA Exoplanet Archive', description: 'Confirmed exoplanet data from the NASA Exoplanet Science Institute.', base_url: 'https://exoplanetarchive.ipac.caltech.edu/TAP', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'Open Notify ISS',        description: 'Real-time position of the International Space Station and crew on board.', base_url: 'http://api.open-notify.org', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'SpaceX API',             description: 'Data on SpaceX launches, rockets, capsules, crew, and Starlink satellites.', base_url: 'https://api.spacexdata.com/v4', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'Newton API',             description: 'Micro-service for advanced math operations — simplify, factor, derive, integrate.', base_url: 'https://newton.vercel.app/api/v2', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'Numbers API',            description: 'Interesting facts about numbers — trivia, math, dates, and years.', base_url: 'http://numbersapi.com', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'Wolfram Alpha',          description: 'Computational intelligence: solve math, science, and data questions via natural language.', base_url: 'https://api.wolframalpha.com/v2', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'USGS Earthquake Hazards',description: 'Real-time earthquake data from the US Geological Survey feed.', base_url: 'https://earthquake.usgs.gov/fdsnws/event/1', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'WoRMS',                  description: 'Authoritative global list of marine species names and taxonomy.', base_url: 'https://www.marinespecies.org/rest', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  // ── Programming & Development ───────────────────────────────
  { name: 'GitHub',                 description: 'Repos, issues, pull requests, Actions, Gists, and more.', base_url: 'https://api.github.com', auth_type: 'token', connector_type: 'api', risk_level: 'medium' },
  { name: 'GitLab',                 description: 'Full DevSecOps platform — repos, CI/CD, merge requests, and packages.', base_url: 'https://gitlab.com/api/v4', auth_type: 'api_key', connector_type: 'api', risk_level: 'medium' },
  { name: 'SerpApi',                description: 'Structured Google, Bing, and DuckDuckGo SERP data via a scraping API.', base_url: 'https://serpapi.com/search', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'Hacker News',            description: 'Official HN API — stories, jobs, polls, comments, and user profiles.', base_url: 'https://hacker-news.firebaseio.com/v0', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'npm Registry',           description: 'Search packages, fetch metadata, download stats from the npm registry.', base_url: 'https://registry.npmjs.org', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'PyPI',                   description: 'Python Package Index — package metadata, releases, and dependencies.', base_url: 'https://pypi.org/pypi', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'Codeforces',             description: 'Competitive programming — problems, submissions, contests, and user ratings.', base_url: 'https://codeforces.com/api', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'JDoodle',                description: 'Online compiler and code execution API — 70+ programming languages.', base_url: 'https://api.jdoodle.com/v1', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  // ── Transportation ──────────────────────────────────────────
  { name: 'Transport for London',   description: 'Live tube, bus, bike, and Elizabeth line data from TfL Unified API.', base_url: 'https://api.tfl.gov.uk', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'OpenSky Network',        description: 'Real-time and historical flight tracking data — global ADS-B coverage.', base_url: 'https://opensky-network.org/api', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'AviationStack',          description: 'Global real-time flight status, airline routes, and airport information.', base_url: 'https://api.aviationstack.com/v1', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'MTA Realtime Feeds',     description: 'NYC subway real-time GTFS and arrival feeds from the Metropolitan Transit Authority.', base_url: 'https://api-endpoint.mta.info/Dataservice', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'BART (SF Bay Area)',      description: 'San Francisco Bay Area Rapid Transit real-time departure estimates and station info.', base_url: 'https://api.bart.gov/api', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'Citybikes',              description: 'Bike-sharing station availability from 400+ networks worldwide.', base_url: 'https://api.citybik.es/v2', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'CarAPI',                 description: 'Make, model, trims and specs for vehicles — developer-friendly vehicle data.', base_url: 'https://carapi.app/api', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'Uber',                   description: 'Request rides, get price estimates, and query trip history via the Uber API.', base_url: 'https://api.uber.com/v1.2', auth_type: 'oauth', connector_type: 'api', risk_level: 'medium' },
  // ── Environment & Climate ───────────────────────────────────
  { name: 'Carbon Interface',       description: 'Estimate carbon emissions for flights, vehicles, electricity, and shipping.', base_url: 'https://www.carboninterface.com/api/v1', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: '1ClickImpact',           description: 'Environmental impact API — tree planting, carbon offsetting, and ocean cleanup.', base_url: 'https://api.1clickimpact.com', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'Global Fishing Watch',   description: 'Vessel tracking, fishing activity detection, and ocean monitoring data.', base_url: 'https://gateway.api.globalfishingwatch.org/v3', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'EPA AQS',                description: 'US EPA Air Quality System — historical and current ambient air monitoring data.', base_url: 'https://aqs.epa.gov/data/api', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  // ── Health ──────────────────────────────────────────────────
  { name: 'Open FDA',               description: 'US FDA data — drug labels, adverse events, recalls, and device reports.', base_url: 'https://api.fda.gov', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'National Library of Medicine UMLS', description: 'Unified Medical Language System — medical concepts, relationships, and terminology.', base_url: 'https://uts-ws.nlm.nih.gov/rest', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'Nutritionix',            description: 'Nutrition data for foods and restaurant menu items — natural language NLP queries.', base_url: 'https://trackapi.nutritionix.com/v2', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'Disease.sh',             description: 'COVID-19 and global disease statistics — countries, vaccines, and historical data.', base_url: 'https://disease.sh/v3', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  // ── Food & Drink ────────────────────────────────────────────
  { name: 'TheMealDB',              description: '1,000+ international recipes with ingredients, measures, and instructional videos.', base_url: 'https://www.themealdb.com/api/json/v1/1', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'TheCocktailDB',          description: 'Cocktail recipes, ingredients, and drink images from a crowd-sourced database.', base_url: 'https://www.thecocktaildb.com/api/json/v1/1', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'Open Food Facts',        description: 'Collaborative food product database — ingredients, nutritional facts, and barcode lookup.', base_url: 'https://world.openfoodfacts.org/api/v3', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'Spoonacular',            description: 'Recipe search, meal planning, ingredient parsing, and wine pairing.', base_url: 'https://api.spoonacular.com', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  // ── Sports & Fitness ────────────────────────────────────────
  { name: 'API-Football',           description: 'Live scores, fixtures, standings, and stats for 900+ football leagues worldwide.', base_url: 'https://v3.football.api-sports.io', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'iSports API',            description: 'Live and historical data for global competitions — scores, fixtures, and player stats.', base_url: 'https://api.isportsapi.com', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'NBA Stats',              description: 'Comprehensive NBA player statistics, advanced metrics, and game data.', base_url: 'https://stats.nba.com/stats', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'Fantasy Premier League', description: 'FPL player data, fixtures, team standings, and gameweek history.', base_url: 'https://fantasy.premierleague.com/api', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'Ergast Motor Racing',    description: 'Formula 1 race data — results, standings, lap times, and pit stops since 1950.', base_url: 'https://ergast.com/api/f1', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  // ── News & Media ────────────────────────────────────────────
  { name: 'NewsAPI',                description: 'Search and retrieve news articles from 150,000+ sources worldwide in real time.', base_url: 'https://newsapi.org/v2', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'World News API',         description: 'Search through millions of semantically tagged worldwide news articles.', base_url: 'https://api.worldnewsapi.com', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'Guardian',               description: 'Full-text access to The Guardian newspaper — 2M+ articles since 1999.', base_url: 'https://content.guardianapis.com', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'New York Times',         description: 'Article search, Top Stories, Books Bestsellers, and Movie Reviews APIs.', base_url: 'https://api.nytimes.com/svc', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  // ── Books & Knowledge ───────────────────────────────────────
  { name: 'Open Library',           description: 'Internet Archive open library — 20M+ book records, covers, and editions.', base_url: 'https://openlibrary.org/api', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'Google Books',           description: 'Search 40M+ books, retrieve metadata, previews, and reading links.', base_url: 'https://www.googleapis.com/books/v1', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'Wikipedia',              description: 'Access Wikipedia article summaries, sections, and linked data via REST.', base_url: 'https://en.wikipedia.org/api/rest_v1', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  // ── Music ───────────────────────────────────────────────────
  { name: 'Spotify',                description: 'Tracks, artists, albums, playlists, audio features, and playback control.', base_url: 'https://api.spotify.com/v1', auth_type: 'oauth', connector_type: 'api', risk_level: 'medium' },
  { name: 'Last.fm',                description: 'Scrobbling, artist bios, top tracks, and music charts from a 50M listener community.', base_url: 'https://ws.audioscrobbler.com/2.0', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'MusicBrainz',            description: 'Open music encyclopedia — artists, recordings, releases, and relationships.', base_url: 'https://musicbrainz.org/ws/2', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  // ── Government & Open Data ──────────────────────────────────
  { name: 'Data USA',               description: 'Visualise and query US demographic, economic, and educational data.', base_url: 'https://datausa.io/api/data', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'US Census Bureau',       description: 'American Community Survey — population, income, housing, and demographics.', base_url: 'https://api.census.gov/data', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'World Bank',             description: 'Global development indicators — GDP, poverty, health, education, and more.', base_url: 'https://api.worldbank.org/v2', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'civicAPI',               description: 'Live and historic election results and voter registration data from around the world.', base_url: 'https://civicapi.com/api', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'Data Commons (Google)',  description: 'Global disaster events, climate, and statistics maintained as an open knowledge graph.', base_url: 'https://api.datacommons.org', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  // ── Finance (non-AI) ────────────────────────────────────────
  { name: 'Stripe',                 description: 'Payment processing, subscriptions, invoices, and billing for businesses.', base_url: 'https://api.stripe.com/v1', auth_type: 'api_key', connector_type: 'api', risk_level: 'high' },
  { name: 'CoinGecko',              description: 'Crypto market data — prices, volumes, OHLC, and market cap for 10,000+ coins.', base_url: 'https://api.coingecko.com/api/v3', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'Alpha Vantage',          description: 'Stock, ETF, forex, and crypto time-series and fundamental data.', base_url: 'https://www.alphavantage.co', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'Polygon.io',             description: 'Real-time and historical US and global stock market data with WebSocket support.', base_url: 'https://api.polygon.io/v2', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'Open Exchange Rates',    description: 'Real-time and historical currency exchange rates for 190+ currencies.', base_url: 'https://openexchangerates.org/api', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  // ── Communication & Messaging ───────────────────────────────
  { name: 'Twilio',                 description: 'SMS, voice, WhatsApp, and email communications at global scale.', base_url: 'https://api.twilio.com/2010-04-01', auth_type: 'api_key', connector_type: 'api', risk_level: 'medium' },
  { name: 'SendGrid',               description: 'Transactional and marketing email delivery API with analytics.', base_url: 'https://api.sendgrid.com/v3', auth_type: 'api_key', connector_type: 'api', risk_level: 'medium' },
  { name: 'Slack',                  description: 'Send messages, create channels, manage workspaces, and build apps.', base_url: 'https://slack.com/api', auth_type: 'oauth', connector_type: 'api', risk_level: 'medium' },
  // ── Geocoding & Maps ────────────────────────────────────────
  { name: 'Mapbox',                 description: 'Custom maps, geocoding, navigation, isochrones, and elevation data.', base_url: 'https://api.mapbox.com', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
  { name: 'OpenStreetMap Nominatim',description: 'Free geocoding and reverse-geocoding based on OpenStreetMap data.', base_url: 'https://nominatim.openstreetmap.org', auth_type: 'none', connector_type: 'api', risk_level: 'low' },
  { name: 'IPinfo',                 description: 'IP geolocation, ASN, carrier, and privacy detection data.', base_url: 'https://ipinfo.io', auth_type: 'api_key', connector_type: 'api', risk_level: 'low' },
];

// ── Curated MCP server catalog ──────────────────────────────────
interface McpServer {
  name: string;
  description: string;
  command: string;
  args: string[];
  env_keys: string[];
  transport: 'stdio' | 'sse';
  category: string;
  risk_level: RiskLevelVal;
  github_url: string;
  npm_package: string;
}

const MCP_SERVERS: McpServer[] = [
  // ── Search ──────────────────────────────────────────────────
  { name: 'Brave Search',        description: 'Web and local search via the Brave Search API.',                                    command: 'npx', args: ['-y', '@modelcontextprotocol/server-brave-search'],   env_keys: ['BRAVE_API_KEY'],                    transport: 'stdio', category: 'Search',        risk_level: 'low',    github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-brave-search' },
  { name: 'Tavily Search',       description: 'AI-optimized search engine for LLMs and RAG pipelines.',                            command: 'npx', args: ['-y', 'tavily-mcp@latest'],                        env_keys: ['TAVILY_API_KEY'],                   transport: 'stdio', category: 'Search',        risk_level: 'low',    github_url: 'https://github.com/tavily-ai/tavily-mcp',                          npm_package: 'tavily-mcp' },
  { name: 'Exa Search',          description: 'Neural search engine for finding relevant content.',                                 command: 'npx', args: ['-y', '@exa-labs/exa-mcp-server'],                  env_keys: ['EXA_API_KEY'],                      transport: 'stdio', category: 'Search',        risk_level: 'low',    github_url: 'https://github.com/exa-labs/exa-mcp-server',                       npm_package: '@exa-labs/exa-mcp-server' },
  { name: 'SerpAPI',             description: 'Google, Bing, Yahoo and other search engine results.',                               command: 'npx', args: ['-y', 'serpapi-mcp-server'],                       env_keys: ['SERPAPI_API_KEY'],                   transport: 'stdio', category: 'Search',        risk_level: 'low',    github_url: 'https://github.com/serpapi/serpapi-mcp',                            npm_package: 'serpapi-mcp-server' },
  // ── Web Scraping ────────────────────────────────────────────
  { name: 'Puppeteer',           description: 'Browser automation and web scraping using Puppeteer.',                               command: 'npx', args: ['-y', '@modelcontextprotocol/server-puppeteer'],    env_keys: [],                                   transport: 'stdio', category: 'Web Scraping',  risk_level: 'medium', github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-puppeteer' },
  { name: 'Playwright',          description: 'Browser automation across Chromium, Firefox, and WebKit.',                           command: 'npx', args: ['-y', '@executeautomation/playwright-mcp-server'],  env_keys: [],                                   transport: 'stdio', category: 'Web Scraping',  risk_level: 'medium', github_url: 'https://github.com/executeautomation/playwright-mcp-server',       npm_package: '@executeautomation/playwright-mcp-server' },
  { name: 'Firecrawl',           description: 'Web scraping and crawling with AI-ready markdown output.',                           command: 'npx', args: ['-y', 'firecrawl-mcp'],                            env_keys: ['FIRECRAWL_API_KEY'],                transport: 'stdio', category: 'Web Scraping',  risk_level: 'medium', github_url: 'https://github.com/mendableai/firecrawl-mcp',                      npm_package: 'firecrawl-mcp' },
  { name: 'Fetch',               description: 'Fetch and convert web pages to markdown or plain text.',                             command: 'npx', args: ['-y', '@modelcontextprotocol/server-fetch'],        env_keys: [],                                   transport: 'stdio', category: 'Web Scraping',  risk_level: 'low',    github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-fetch' },
  // ── Development ─────────────────────────────────────────────
  { name: 'GitHub',              description: 'Repository management, file operations, issues, PRs, and more.',                     command: 'npx', args: ['-y', '@modelcontextprotocol/server-github'],       env_keys: ['GITHUB_PERSONAL_ACCESS_TOKEN'],     transport: 'stdio', category: 'Development',   risk_level: 'medium', github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-github' },
  { name: 'GitLab',              description: 'Project management, issues, merge requests, and CI/CD on GitLab.',                   command: 'npx', args: ['-y', '@modelcontextprotocol/server-gitlab'],       env_keys: ['GITLAB_PERSONAL_ACCESS_TOKEN', 'GITLAB_API_URL'], transport: 'stdio', category: 'Development',   risk_level: 'medium', github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-gitlab' },
  { name: 'Context7',            description: 'Up-to-date, version-specific library docs and code examples.',                       command: 'npx', args: ['-y', '@upstash/context7-mcp@latest'],              env_keys: [],                                   transport: 'stdio', category: 'Development',   risk_level: 'low',    github_url: 'https://github.com/upstash/context7-mcp',                          npm_package: '@upstash/context7-mcp' },
  { name: 'Sentry',              description: 'Error monitoring, performance data, and issue management.',                          command: 'npx', args: ['-y', '@sentry/mcp-server'],                       env_keys: ['SENTRY_AUTH_TOKEN'],                 transport: 'stdio', category: 'Development',   risk_level: 'low',    github_url: 'https://github.com/getsentry/sentry-mcp',                          npm_package: '@sentry/mcp-server' },
  // ── Database ────────────────────────────────────────────────
  { name: 'PostgreSQL',          description: 'Query and manage PostgreSQL databases with schema inspection.',                      command: 'npx', args: ['-y', '@modelcontextprotocol/server-postgres'],     env_keys: ['POSTGRES_CONNECTION_STRING'],        transport: 'stdio', category: 'Database',      risk_level: 'high',   github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-postgres' },
  { name: 'SQLite',              description: 'Query and manage SQLite databases and run business analytics.',                      command: 'npx', args: ['-y', '@modelcontextprotocol/server-sqlite'],       env_keys: ['SQLITE_DB_PATH'],                   transport: 'stdio', category: 'Database',      risk_level: 'medium', github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-sqlite' },
  { name: 'MySQL',               description: 'Query and manage MySQL databases.',                                                  command: 'npx', args: ['-y', '@benborla29/mcp-server-mysql'],              env_keys: ['MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE'], transport: 'stdio', category: 'Database', risk_level: 'high', github_url: 'https://github.com/benborla/mcp-server-mysql', npm_package: '@benborla29/mcp-server-mysql' },
  { name: 'MongoDB',             description: 'CRUD operations, aggregation, and index management for MongoDB.',                    command: 'npx', args: ['-y', 'mongodb-mcp-server'],                       env_keys: ['MONGODB_URI'],                      transport: 'stdio', category: 'Database',      risk_level: 'high',   github_url: 'https://github.com/mongodb-js/mongodb-mcp-server',                 npm_package: 'mongodb-mcp-server' },
  { name: 'Redis',               description: 'Key-value operations, pub/sub, and data structure management.',                      command: 'npx', args: ['-y', '@modelcontextprotocol/server-redis'],        env_keys: ['REDIS_URL'],                        transport: 'stdio', category: 'Database',      risk_level: 'medium', github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-redis' },
  { name: 'Supabase',            description: 'Database, auth, storage, and edge functions on Supabase.',                           command: 'npx', args: ['-y', '@supabase/mcp-server-supabase@latest'],      env_keys: ['SUPABASE_ACCESS_TOKEN'],             transport: 'stdio', category: 'Database',      risk_level: 'high',   github_url: 'https://github.com/supabase-community/supabase-mcp',               npm_package: '@supabase/mcp-server-supabase' },
  // ── Productivity ────────────────────────────────────────────
  { name: 'Slack',               description: 'Send messages, manage channels, and search across workspaces.',                      command: 'npx', args: ['-y', '@modelcontextprotocol/server-slack'],        env_keys: ['SLACK_BOT_TOKEN', 'SLACK_TEAM_ID'], transport: 'stdio', category: 'Productivity',  risk_level: 'medium', github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-slack' },
  { name: 'Google Drive',        description: 'Search, read, and manage files in Google Drive.',                                    command: 'npx', args: ['-y', '@modelcontextprotocol/server-gdrive'],       env_keys: ['GDRIVE_CREDENTIALS_PATH'],          transport: 'stdio', category: 'Productivity',  risk_level: 'medium', github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-gdrive' },
  { name: 'Notion',              description: 'Search, read, create, and update pages and databases in Notion.',                    command: 'npx', args: ['-y', '@notionhq/notion-mcp-server'],              env_keys: ['NOTION_API_KEY'],                   transport: 'stdio', category: 'Productivity',  risk_level: 'medium', github_url: 'https://github.com/makenotion/notion-mcp-server',                  npm_package: '@notionhq/notion-mcp-server' },
  { name: 'Linear',              description: 'Manage issues, projects, and teams in Linear.',                                      command: 'npx', args: ['-y', '@linear/mcp-server'],                       env_keys: ['LINEAR_API_KEY'],                   transport: 'stdio', category: 'Productivity',  risk_level: 'medium', github_url: 'https://github.com/linear/linear-mcp-server',                      npm_package: '@linear/mcp-server' },
  { name: 'Todoist',             description: 'Manage tasks, projects, and labels in Todoist.',                                     command: 'npx', args: ['-y', '@abhiz123/todoist-mcp-server'],              env_keys: ['TODOIST_API_TOKEN'],                 transport: 'stdio', category: 'Productivity',  risk_level: 'low',    github_url: 'https://github.com/abhiz123/todoist-mcp-server',                   npm_package: '@abhiz123/todoist-mcp-server' },
  { name: 'Atlassian',           description: 'Manage Jira issues, Confluence pages, and Opsgenie alerts.',                         command: 'npx', args: ['-y', '@anthropic/atlassian-mcp-server'],           env_keys: ['ATLASSIAN_API_TOKEN', 'ATLASSIAN_EMAIL', 'ATLASSIAN_DOMAIN'], transport: 'stdio', category: 'Productivity', risk_level: 'medium', github_url: 'https://github.com/atlassian/atlassian-mcp-server', npm_package: '@anthropic/atlassian-mcp-server' },
  // ── Communication ───────────────────────────────────────────
  { name: 'Gmail',               description: 'Send, read, search, and manage emails via Gmail API.',                               command: 'npx', args: ['-y', '@anthropic/gmail-mcp-server'],               env_keys: ['GMAIL_CREDENTIALS_PATH'],            transport: 'stdio', category: 'Communication', risk_level: 'high',   github_url: 'https://github.com/anthropics/gmail-mcp-server',                   npm_package: '@anthropic/gmail-mcp-server' },
  { name: 'Discord',             description: 'Send and read messages, manage channels in Discord.',                                command: 'npx', args: ['-y', 'discord-mcp'],                              env_keys: ['DISCORD_BOT_TOKEN'],                 transport: 'stdio', category: 'Communication', risk_level: 'medium', github_url: 'https://github.com/v-3/discord-mcp',                               npm_package: 'discord-mcp' },
  // ── Cloud Services ──────────────────────────────────────────
  { name: 'AWS',                 description: 'Manage AWS resources and services via CLI commands.',                                 command: 'npx', args: ['-y', '@aws/aws-mcp-server'],                      env_keys: ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION'], transport: 'stdio', category: 'Cloud', risk_level: 'critical', github_url: 'https://github.com/awslabs/mcp',                    npm_package: '@aws/aws-mcp-server' },
  { name: 'Cloudflare',          description: 'Deploy and configure Workers, KV, R2, D1 on Cloudflare.',                            command: 'npx', args: ['-y', '@cloudflare/mcp-server-cloudflare'],         env_keys: ['CLOUDFLARE_API_TOKEN'],              transport: 'stdio', category: 'Cloud',         risk_level: 'high',   github_url: 'https://github.com/cloudflare/mcp-server-cloudflare',              npm_package: '@cloudflare/mcp-server-cloudflare' },
  { name: 'Vercel',              description: 'Manage deployments, projects, and domains on Vercel.',                                command: 'npx', args: ['-y', '@vercel/mcp-adapter'],                      env_keys: ['VERCEL_TOKEN'],                      transport: 'stdio', category: 'Cloud',         risk_level: 'high',   github_url: 'https://github.com/vercel/mcp-adapter',                            npm_package: '@vercel/mcp-adapter' },
  { name: 'Docker',              description: 'Manage containers, images, volumes, and networks.',                                   command: 'npx', args: ['-y', '@modelcontextprotocol/server-docker'],       env_keys: [],                                   transport: 'stdio', category: 'Cloud',         risk_level: 'high',   github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-docker' },
  // ── File System ─────────────────────────────────────────────
  { name: 'Filesystem',          description: 'Secure file operations with configurable access controls.',                           command: 'npx', args: ['-y', '@modelcontextprotocol/server-filesystem'],   env_keys: [],                                   transport: 'stdio', category: 'File System',   risk_level: 'medium', github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-filesystem' },
  { name: 'Google Cloud Storage', description: 'Read and write files in Google Cloud Storage buckets.',                             command: 'npx', args: ['-y', '@modelcontextprotocol/server-gcs'],          env_keys: ['GCS_CREDENTIALS_PATH'],              transport: 'stdio', category: 'File System',   risk_level: 'medium', github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-gcs' },
  // ── Finance ─────────────────────────────────────────────────
  { name: 'Stripe',              description: 'Manage payments, customers, invoices, and subscriptions.',                            command: 'npx', args: ['-y', '@stripe/mcp@latest'],                       env_keys: ['STRIPE_SECRET_KEY'],                 transport: 'stdio', category: 'Finance',       risk_level: 'critical', github_url: 'https://github.com/stripe/agent-toolkit',                         npm_package: '@stripe/mcp' },
  // ── AI / Memory ─────────────────────────────────────────────
  { name: 'Qdrant',              description: 'Vector search, similarity queries, and collection management.',                       command: 'npx', args: ['-y', '@qdrant/mcp-server-qdrant'],                 env_keys: ['QDRANT_URL', 'QDRANT_API_KEY'],      transport: 'stdio', category: 'AI / Memory',   risk_level: 'medium', github_url: 'https://github.com/qdrant/mcp-server-qdrant',                      npm_package: '@qdrant/mcp-server-qdrant' },
  { name: 'Memory',              description: 'Persistent memory using a local knowledge graph.',                                    command: 'npx', args: ['-y', '@modelcontextprotocol/server-memory'],       env_keys: [],                                   transport: 'stdio', category: 'AI / Memory',   risk_level: 'low',    github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-memory' },
  // ── Utilities ───────────────────────────────────────────────
  { name: 'Sequential Thinking', description: 'Dynamic, reflection-based problem-solving through thought sequences.',               command: 'npx', args: ['-y', '@modelcontextprotocol/server-sequential-thinking'], env_keys: [],                            transport: 'stdio', category: 'Utilities',     risk_level: 'low',    github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-sequential-thinking' },
  { name: 'Everything',          description: 'Reference MCP server that demonstrates all protocol features.',                       command: 'npx', args: ['-y', '@modelcontextprotocol/server-everything'],   env_keys: [],                                   transport: 'stdio', category: 'Utilities',     risk_level: 'low',    github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-everything' },
  { name: 'Time',                description: 'Get current time and convert between time zones.',                                    command: 'npx', args: ['-y', '@modelcontextprotocol/server-time'],         env_keys: [],                                   transport: 'stdio', category: 'Utilities',     risk_level: 'low',    github_url: 'https://github.com/modelcontextprotocol/servers',                   npm_package: '@modelcontextprotocol/server-time' },
];


// ── Slug generator ───────────────────────────────────────────────
const toSlug = (name: string) =>
  name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

// ── Risk level colour ────────────────────────────────────────────
const riskColor = (r: RiskLevelVal) => {
  const map: Record<RiskLevelVal, string> = {
    low:      'text-green-400 border-green-400/30 bg-green-400/5',
    medium:   'text-yellow-400 border-yellow-400/30 bg-yellow-400/5',
    high:     'text-orange-400 border-orange-400/30 bg-orange-400/5',
    critical: 'text-red-400 border-red-400/30 bg-red-400/5',
  };
  return map[r];
};

export function Katana() {
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<TabType>('providers');

  useEffect(() => {
    const syncTabFromHash = () => {
      const requested = window.location.hash.replace('#', '') as TabType;
      if (['providers', 'tools', 'files', 'routing', 'skills', 'team', 'telegram', 'teams', 'mail_calendar', 'office', 'ide', 'mado', 'ronin', 'skillopt'].includes(requested)) {
        setActiveTab(requested);
      }
    };
    syncTabFromHash();
    window.addEventListener('hashchange', syncTabFromHash);
    return () => window.removeEventListener('hashchange', syncTabFromHash);
  }, []);
  const { t } = useTranslation();

  // ── Telegram state ──────────────────────────────────────────────
  const [tgStatus, setTgStatus]         = useState<any>(null);
  const [tgToken, setTgToken]           = useState('');
  const [tgMode, setTgMode]             = useState<'polling' | 'webhook'>('polling');
  const [tgWebhook, setTgWebhook]       = useState('');
  const [tgChatIds, setTgChatIds]       = useState('');
  const [tgTestChat, setTgTestChat]     = useState('');
  const [tgSaving, setTgSaving]         = useState(false);
  const [tgTesting, setTgTesting]       = useState(false);
  const [tgTestResult, setTgTestResult] = useState<{ ok: boolean; message?: string; error?: string } | null>(null);
  const [tgDetecting, setTgDetecting]   = useState(false);
  const [tgShowToken, setTgShowToken]   = useState(false);
  const [tgTopicGroups, setTgTopicGroups] = useState<any[]>([]);
  const [tgTopicDrafts, setTgTopicDrafts] = useState<Record<string, string>>({});
  const [tgTopicSaving, setTgTopicSaving] = useState<string | null>(null);

  // ── Mail & Calendar state ──────────────────────────────────────
  const [mailAccount, setMailAccount] = useState<any>(null);
  const [mailForm, setMailForm] = useState({
    provider: 'gmail',
    display_name: '',
    email_address: '',
    protocol: 'imap',
    imap_host: 'imap.gmail.com',
    imap_port: 993,
    imap_use_ssl: true,
    smtp_host: 'smtp.gmail.com',
    smtp_port: 587,
    smtp_use_ssl: true,
    username: '',
    password: '',
    caldav_url: '',
    calendar_provider: 'google_api',
    calendar_credentials: null as any,
  });
  const [mailSaving, setMailSaving] = useState(false);
  const [mailTesting, setMailTesting] = useState(false);
  const [mailTestResult, setMailTestResult] = useState<{ ok: boolean; imap_ok: boolean; smtp_ok: boolean; message?: string } | null>(null);
  const [showMailPassword, setShowMailPassword] = useState(false);

  // ── Office App Mode state ─────────────────────────────────────
  const [officeStatus, setOfficeStatus] = useState<any>(null);
  const [officeConfig, setOfficeConfig] = useState<any>(null);
  const [officePosture, setOfficePosture] = useState<string>('');
  const [officeSaving, setOfficeSaving] = useState(false);
  const [officeDetecting, setOfficeDetecting] = useState(false);
  const [officeUnsaved, setOfficeUnsaved] = useState(false);

  const fetchOfficeData = async () => {
    try {
      const [statusRes, configRes, postureRes] = await Promise.all([
        axios.get('/api/v1/office/status'),
        axios.get('/api/v1/office/config'),
        axios.get('/api/v1/security/posture'),
      ]);
      if (statusRes.data?.success) setOfficeStatus(statusRes.data.data);
      if (configRes.data?.success) setOfficeConfig(configRes.data.data);
      if (postureRes.data?.data?.active_tier) setOfficePosture(postureRes.data.data.active_tier);
    } catch (err) {
      console.error('Failed to load Office data:', err);
    }
  };

  const saveOfficeConfig = async () => {
    if (!officeConfig) return;
    setOfficeSaving(true);
    try {
      const res = await axios.post('/api/v1/office/config', officeConfig);
      if (res.data?.success) {
        setOfficeConfig(res.data.data);
        setOfficeUnsaved(false);
        setStatusMessage({ type: 'success', text: 'Office configuration saved' });
        setTimeout(() => setStatusMessage(null), 3000);
      }
    } catch (err) {
      setStatusMessage({ type: 'error', text: 'Failed to save Office configuration' });
      setTimeout(() => setStatusMessage(null), 3000);
    } finally {
      setOfficeSaving(false);
    }
  };

  const detectOfficeApps = async () => {
    setOfficeDetecting(true);
    try {
      await axios.post('/api/v1/office/detect');
      await fetchOfficeData();
    } catch (err) {
      console.error('Detection failed:', err);
    } finally {
      setOfficeDetecting(false);
    }
  };

  const updateOfficeConfig = (path: string, value: any) => {
    if (!officeConfig) return;
    const updated = setSafeObjectPath(officeConfig, path, value);
    setOfficeConfig(updated);
    setOfficeUnsaved(true);
  };

  const [loading, setLoading]     = useState(true);
  const [saving, setSaving]       = useState(false);

  const [providers, setProviders]   = useState<any[]>([]);
  const [tools, setTools]           = useState<any[]>([]);
  const [localModels, setLocalModels] = useState<string[]>([]);
  const [localProviderType, setLocalProviderType] = useState<string>('ollama');
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);

  // ── New Provider form state ──────────────────────────────────
  const [newProvider, setNewProvider] = useState({
    name: '',
    provider_type: 'openai',
    auth_type: 'api_key',
    api_key: '',
    base_url: PROVIDER_BASE_URLS['openai'],
    is_active: true
  });
  const [configuredModels, setConfiguredModels] = useState<string[]>([]);
  const [customModelInput, setCustomModelInput] = useState('');
  const [providerConfigBase, setProviderConfigBase] = useState<Record<string, any>>({});
  const [baseUrlOverride, setBaseUrlOverride] = useState(false);
  const [localModelPath, setLocalModelPath]   = useState('');
  const [scanningModels, setScanningModels]   = useState(false);

  // ── Pull-model state ─────────────────────────────────────────
  const [showPullPanel, setShowPullPanel]         = useState(false);
  
  useEffect(() => {
    const activeLocal = providers.find(p => p.status === 'connected' && isLocalProvider(p.provider_type));
    const isLocal = isLocalProvider(newProvider.provider_type);
    
    if (isLocal) {
      fetchLocalModels(newProvider.provider_type, newProvider.base_url);
      // Set a sensible default path when switching to a local provider
      if (!localModelPath) {
        if (newProvider.provider_type === 'ollama') {
          // Windows default; user can override
          setLocalModelPath('%USERPROFILE%\\.ollama\\models');
        } else {
          setLocalModelPath('');
        }
      }
    } else if (activeLocal) {
      fetchLocalModels(activeLocal.provider_type, activeLocal.base_url);
    } else {
      setLocalModels([]);
      setLocalModelPath('');
    }
  }, [newProvider.provider_type, newProvider.base_url, providers]);

  const [pullCatalogFilter, setPullCatalogFilter] = useState<string>('all');
  const [pullingModel, setPullingModel]           = useState<string | null>(null);
  const [pullStatus, setPullStatus]               = useState<{ status: string; percent: number } | null>(null);
  const [customPullTag, setCustomPullTag]         = useState('');

  // ── Live Ollama search state ──────────────────────────────────
  const [ollamaQuery, setOllamaQuery]             = useState('');
  const [ollamaResults, setOllamaResults]         = useState<OllamaSearchResult[]>([]);
  const [ollamaLoading, setOllamaLoading]         = useState(false);
  const [ollamaPage, setOllamaPage]               = useState(1);
  const [ollamaHasMore, setOllamaHasMore]         = useState(false);
  const [ollamaLoadingMore, setOllamaLoadingMore] = useState(false);

  const searchOllamaModels = async (query: string, page: number, append: boolean = false) => {
    if (page === 1) setOllamaLoading(true);
    else setOllamaLoadingMore(true);
    try {
      const params: Record<string, string> = {};
      if (query.trim()) params.q = query.trim();
      if (page > 1) params.p = String(page);
      if (pullCatalogFilter !== 'all') params.c = pullCatalogFilter;
      const res = await axios.get('/api/v1/system/ollama-search', { params });
      if (res.data?.success) {
        const data = res.data.data;
        setOllamaResults(prev => append ? [...prev, ...data.models] : data.models);
        setOllamaHasMore(data.has_more);
        setOllamaPage(data.page);
      }
    } catch {
      if (!append) setOllamaResults([]);
    } finally {
      setOllamaLoading(false);
      setOllamaLoadingMore(false);
    }
  };

  // Debounced search when query or filter changes
  useEffect(() => {
    if (!showPullPanel) return;
    const timer = setTimeout(() => {
      searchOllamaModels(ollamaQuery, 1, false);
    }, 300);
    return () => clearTimeout(timer);
  }, [ollamaQuery, pullCatalogFilter, showPullPanel]);

  // Initial load when panel opens
  useEffect(() => {
    if (showPullPanel && ollamaResults.length === 0) {
      searchOllamaModels('', 1, false);
    }
  }, [showPullPanel]);

  // ── Register Tool panel state ────────────────────────────────
  const [showRegisterTool, setShowRegisterTool] = useState(false);
  const [registerMode, setRegisterMode]         = useState<RegisterMode>('quick');
  const [apiSearch, setApiSearch]               = useState('');
  const [selectedApi, setSelectedApi]           = useState<PublicApi | null>(null);
  const [registerSaving, setRegisterSaving]     = useState(false);
  const [quickApiKey, setQuickApiKey]           = useState('');
  const [newTool, setNewTool] = useState<{
    name: string;
    slug: string;
    base_url: string;
    connector_type: ConnectorTypeVal;
    auth_type: AuthTypeVal;
    risk_level: RiskLevelVal;
  }>({
    name: '',
    slug: '',
    base_url: '',
    connector_type: 'api',
    auth_type: 'api_key',
    risk_level: 'low',
  });


  // ── MCP Server state ─────────────────────────────────────────
  const [showRegisterMcp, setShowRegisterMcp] = useState(false);
  const [mcpRegisterMode, setMcpRegisterMode] = useState<'quick' | 'manual'>('quick');
  const [mcpSearch, setMcpSearch]             = useState('');
  const [selectedMcp, setSelectedMcp]         = useState<McpServer | null>(null);
  const [mcpEnvValues, setMcpEnvValues]       = useState<Record<string, string>>({});
  const [newMcp, setNewMcp] = useState({
    name: '',
    command: '',
    args: '',
    transport: 'stdio' as 'stdio' | 'sse',
    risk_level: 'medium' as RiskLevelVal
  });

  const filteredMcps = useMemo(() => {
    if (!mcpSearch.trim()) return MCP_SERVERS;
    const q = mcpSearch.toLowerCase();
    return MCP_SERVERS.filter(m => 
      m.name.toLowerCase().includes(q) || m.description.toLowerCase().includes(q) || m.category.toLowerCase().includes(q)
    );
  }, [mcpSearch]);

  // ── Routing profile state ────────────────────────────────────
  const [routingProfiles, setRoutingProfiles]   = useState<any[]>([]);
  const [showCreateProfile, setShowCreateProfile] = useState(false);
  const [showRoutingProfileEditor, setShowRoutingProfileEditor] = useState(false);
  const [profileSaving, setProfileSaving]       = useState(false);
  const [expandedProfileId, setExpandedProfileId] = useState<string | null>(null);
  const [showAddRule, setShowAddRule]           = useState(false);
  const [newProfile, setNewProfile]             = useState({ name: '', description: '', is_default: false });
  const [newRule, setNewRule]                   = useState({
    task_type: '*',
    primary_model_id: '',
    fallback_model_ids: [] as string[],
    latency_bias: '' as string,
    cost_bias: '' as string,
  });
  const [editingRuleIdx, setEditingRuleIdx]     = useState<number | null>(null);

  useEffect(() => { fetchData(); }, []);



  const fetchData = async () => {
    setLoading(true);
    try {
      const [provRes, toolRes, routeRes] = await Promise.all([
        axios.get('/api/v1/model-providers'),
        axios.get('/api/v1/tools'),
        axios.get('/api/v1/model-routing-profiles'),
      ]);
      setProviders(provRes.data.data || []);
      setTools(toolRes.data.data || []);
      setRoutingProfiles(routeRes.data.data || []);
    } catch (error) {
      console.error('Error fetching Katana data:', error);
    } finally {
      setLoading(false);
    }
  };

  // ── Telegram handlers ────────────────────────────────────────
  const fetchTgStatus = async () => {
    try {
      const [res, topicsRes] = await Promise.all([
        axios.get('/api/v1/channels/telegram/status'),
        axios.get('/api/v1/channels/telegram/topics'),
      ]);
      const d = res.data.data;
      setTgStatus(d);
      if (d?.mode) setTgMode(d.mode);
      if (d?.allowed_chat_ids?.length) setTgChatIds(d.allowed_chat_ids.join(', '));
      if (d?.webhook_url) setTgWebhook(d.webhook_url || '');
      const groups = topicsRes.data.data || [];
      setTgTopicGroups(groups);
      const drafts: Record<string, string> = {};
      groups.forEach((group: any) => (group.topics || []).forEach((topic: any) => {
        drafts[`${group.chat_id}:${topic.message_thread_id}`] = topic.name || '';
      }));
      setTgTopicDrafts(drafts);
    } catch { /* ignore */ }
  };

  const handleSaveTgTopic = async (chatId: string, threadId: number) => {
    const key = `${chatId}:${threadId}`;
    const name = (tgTopicDrafts[key] || '').trim();
    if (!name) return;
    setTgTopicSaving(key);
    try {
      await axios.put(`/api/v1/channels/telegram/topics/${encodeURIComponent(chatId)}/${threadId}`, { name });
      await fetchTgStatus();
      setStatusMessage({ type: 'success', text: `Telegram topic ${threadId} mapped to “${name}”.` });
    } catch (error: any) {
      setStatusMessage({ type: 'error', text: error?.response?.data?.detail || 'Topic mapping could not be saved.' });
    } finally {
      setTgTopicSaving(null);
      setTimeout(() => setStatusMessage(null), 4000);
    }
  };

  const handleTgConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tgToken.trim()) return;
    setTgSaving(true);
    try {
      const res = await axios.post('/api/v1/channels/telegram/connect', {
        bot_token: tgToken.trim(),
        mode: tgMode,
        allowed_chat_ids: tgChatIds.split(',').map((s: string) => s.trim()).filter(Boolean),
        webhook_url: tgMode === 'webhook' ? tgWebhook.trim() : null,
      });
      const d = res.data.data;
      setTgStatus(d);
      if (!d.connected) {
        setStatusMessage({ type: 'error', text: d.error || t('katana.connection_failed') });
      } else {
        setStatusMessage({ type: 'success', text: `Connected as @${d.bot_username}` });
        setTgToken('');
      }
    } catch {
      setStatusMessage({ type: 'error', text: t('katana.connect_failed') });
    } finally {
      setTgSaving(false);
      setTimeout(() => setStatusMessage(null), 4000);
    }
  };

  const handleTgTest = async () => {
    if (!tgTestChat.trim()) return;
    setTgTesting(true);
    setTgTestResult(null);
    try {
      const res = await axios.post('/api/v1/channels/telegram/test', { chat_id: tgTestChat.trim() });
      setTgTestResult(res.data.data);
    } catch (e: any) {
      setTgTestResult({ ok: false, error: e.message || 'Request failed' });
    } finally {
      setTgTesting(false);
    }
  };

  const handleTgDetect = async () => {
    setTgDetecting(true);
    setTgTestResult(null);
    try {
      const res = await axios.post('/api/v1/channels/telegram/detect');
      const data = res.data.data;
      if (data.ok && data.chat_id) {
        setTgTestChat(data.chat_id);
        const currentWhitelisted = tgChatIds.split(',').map(s => s.trim()).filter(Boolean);
        if (!currentWhitelisted.includes(data.chat_id)) {
          currentWhitelisted.push(data.chat_id);
          setTgChatIds(currentWhitelisted.join(', '));
        }
        setTgTestResult({ ok: true, message: `Auto-detected ID ${data.chat_id} from ${data.name}!` });
      } else {
        setTgTestResult({ ok: false, error: data.error || 'Could not detect ID.' });
      }
    } catch (e: any) {
      setTgTestResult({ ok: false, error: e.message || 'Request failed' });
    } finally {
      setTgDetecting(false);
    }
  };

  const handleTgDisconnect = async () => {
    if (!confirm(t('katana.disconnect_confirm'))) return;
    try {
      await axios.delete('/api/v1/channels/telegram/disconnect');
      setTgStatus(null);
      setTgChatIds('');
      setTgWebhook('');
      setTgTestResult(null);
      setStatusMessage({ type: 'success', text: t('katana.bot_disconnected') });
    } catch {
      setStatusMessage({ type: 'error', text: t('katana.disconnect_failed') });
    } finally {
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  // ── Mail & Calendar handlers ────────────────────────────────────────
  useEffect(() => {
    const prov = mailForm.provider;
    if (prov === 'gmail') {
      setMailForm(f => ({
        ...f,
        imap_host: 'imap.gmail.com',
        imap_port: 993,
        imap_use_ssl: true,
        smtp_host: 'smtp.gmail.com',
        smtp_port: 587,
        smtp_use_ssl: true,
        caldav_url: '',
        calendar_provider: 'google_api',
      }));
    } else if (prov === 'outlook') {
      setMailForm(f => ({
        ...f,
        imap_host: 'outlook.office365.com',
        imap_port: 993,
        imap_use_ssl: true,
        smtp_host: 'smtp.office365.com',
        smtp_port: 587,
        smtp_use_ssl: true,
        caldav_url: '',
        calendar_provider: 'microsoft_graph',
      }));
    } else if (prov === 'proton') {
      setMailForm(f => ({
        ...f,
        imap_host: '127.0.0.1',
        imap_port: 1143,
        imap_use_ssl: false,
        smtp_host: '127.0.0.1',
        smtp_port: 1025,
        smtp_use_ssl: false,
        caldav_url: 'http://127.0.0.1:5000',
        calendar_provider: 'caldav',
      }));
    }
  }, [mailForm.provider]);

  const fetchMailStatus = async () => {
    try {
      const res = await axios.get('/api/v1/channels/email/account');
      const acc = res.data.data;
      setMailAccount(acc);
      if (acc) {
        setMailForm({
          provider: acc.provider,
          display_name: acc.display_name || '',
          email_address: acc.email_address || '',
          protocol: acc.protocol || 'imap',
          imap_host: acc.imap_host || '',
          imap_port: acc.imap_port || 993,
          imap_use_ssl: acc.imap_use_ssl ?? true,
          smtp_host: acc.smtp_host || '',
          smtp_port: acc.smtp_port || 587,
          smtp_use_ssl: acc.smtp_use_ssl ?? true,
          username: acc.username || '',
          password: '',
          caldav_url: acc.caldav_url || '',
          calendar_provider: acc.calendar_provider || 'none',
          calendar_credentials: acc.calendar_credentials || null,
        });
      }
    } catch { /* ignore */ }
  };

  const handleMailConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mailForm.email_address || !mailForm.username || (!mailAccount && !mailForm.password)) return;
    setMailSaving(true);
    try {
      const res = await axios.post('/api/v1/channels/email/account', mailForm);
      const acc = res.data.data;
      setMailAccount(acc);
      setStatusMessage({ type: 'success', text: 'Mail & Calendar account connected!' });
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to connect account' });
    } finally {
      setMailSaving(false);
      setTimeout(() => setStatusMessage(null), 4000);
    }
  };

  const handleMailDisconnect = async () => {
    if (!confirm('Are you sure you want to disconnect this Mail & Calendar account?')) return;
    try {
      await axios.delete('/api/v1/channels/email/account');
      setMailAccount(null);
      setMailForm({
        provider: 'gmail',
        display_name: '',
        email_address: '',
        protocol: 'imap',
        imap_host: 'imap.gmail.com',
        imap_port: 993,
        imap_use_ssl: true,
        smtp_host: 'smtp.gmail.com',
        smtp_port: 587,
        smtp_use_ssl: true,
        username: '',
        password: '',
        caldav_url: '',
        calendar_provider: 'google_api',
        calendar_credentials: null,
      });
      setStatusMessage({ type: 'success', text: 'Mail & Calendar account disconnected.' });
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to disconnect account.' });
    } finally {
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  const handleMailTest = async () => {
    setMailTesting(true);
    setMailTestResult(null);
    try {
      const res = await axios.post('/api/v1/channels/email/account/test', mailForm);
      setMailTestResult(res.data.data);
    } catch (e: any) {
      setMailTestResult({ ok: false, imap_ok: false, smtp_ok: false, message: e.response?.data?.detail || e.message || 'Test request failed' });
    } finally {
      setMailTesting(false);
    }
  };

  const fetchLocalModels = async (providerType: string, customBaseUrl?: string) => {
    setLocalProviderType(providerType);
    try {
      const baseUrl = customBaseUrl || 
        (newProvider.provider_type === providerType ? newProvider.base_url : null) || 
        (providerType === 'ollama' ? 'http://127.0.0.1:11434' : 'http://localhost:1234/v1');

      const res = await axios.get('/api/v1/system/local-models', {
        params: {
          provider_type: providerType,
          base_url: baseUrl,
        }
      });
      if (res.data?.success) {
        setLocalModels(res.data.data || []);
      } else {
        setLocalModels([]);
      }
    } catch {
      setLocalModels([]);
    }
  };

  // Scan the filesystem path via the backend endpoint
  const handleScanLocalModels = async () => {
    const rawPath = localModelPath.trim();
    if (!rawPath) return;
    setScanningModels(true);
    try {
      const res = await axios.get('/api/v1/system/scan-local-models', {
        params: { path: rawPath },
      });
      const found: string[] = res.data?.data || [];
      if (found.length > 0) {
        setLocalModels(found);
        setStatusMessage({ type: 'success', text: `Found ${found.length} model${found.length !== 1 ? 's' : ''} in directory.` });
      } else {
        setStatusMessage({ type: 'error', text: 'No models found at that path. Check the directory and try again.' });
      }
    } catch {
      setStatusMessage({ type: 'error', text: 'Could not scan directory. Ensure the backend can access the path.' });
    } finally {
      setScanningModels(false);
      setTimeout(() => setStatusMessage(null), 4000);
    }
  };

  // Stream an Ollama model pull via SSE backend proxy
  const handlePullModel = async (modelId: string) => {
    const baseUrl = (newProvider.provider_type === 'ollama' ? newProvider.base_url : null) || 'http://127.0.0.1:11434';
    setPullingModel(modelId);
    setPullStatus({ status: 'Connecting to Ollama…', percent: 0 });
    try {
      const params = new URLSearchParams({ model: modelId, base_url: baseUrl });
      const response = await fetch(`/api/v1/system/pull-model?${params}`);
      if (!response.body) throw new Error('No response body');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.slice(6));
            if (data.status === 'error') {
              setStatusMessage({ type: 'error', text: data.error || `Failed to pull ${modelId}` });
              setTimeout(() => setStatusMessage(null), 6000);
              return;
            }
            if (data.status === 'done' || data.status === 'success') {
              setPullStatus({ status: '✓ Complete!', percent: 100 });
              setStatusMessage({ type: 'success', text: `${modelId} pulled successfully — ready to use.` });
              setLocalModels(prev => prev.includes(modelId) ? prev : [modelId, ...prev]);
              setTimeout(() => setStatusMessage(null), 5000);
              break;
            }
            const percent = data.total && data.completed
              ? Math.round((data.completed / data.total) * 100)
              : 0;
            const gbDone = data.completed ? (data.completed / 1e9).toFixed(2) : null;
            const gbTotal = data.total ? (data.total / 1e9).toFixed(2) : null;
            const sizeStr = gbDone && gbTotal ? ` — ${gbDone} / ${gbTotal} GB` : '';
            setPullStatus({ status: `${data.status}${sizeStr}`, percent });
          } catch { /* malformed line, skip */ }
        }
      }
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err?.message || `Failed to pull ${modelId}. Is Ollama running at ${baseUrl}?` });
      setTimeout(() => setStatusMessage(null), 6000);
    } finally {
      setPullingModel(null);
      setPullStatus(null);
    }
  };

  // ── Delete local model ──────────────────────────────────────────
  const [deletingModel, setDeletingModel] = useState<string | null>(null);

  const handleDeleteOllamaModel = async (modelId: string) => {
    if (!confirm(`Delete model "${modelId}" from Ollama? This will free disk space but the model will need to be re-pulled to use again.`)) return;
    const activeOllama = providers.find(p => p.provider_type === 'ollama' && p.base_url);
    const baseUrl = activeOllama?.base_url || 
      (newProvider.provider_type === 'ollama' ? newProvider.base_url : null) || 
      'http://127.0.0.1:11434';
    setDeletingModel(modelId);
    try {
      const params = new URLSearchParams({ model: modelId, base_url: baseUrl });
      const resp = await fetch(`/api/v1/system/delete-model?${params}`, { method: 'DELETE' });
      const data = await resp.json();
      if (data.success) {
        setLocalModels(prev => prev.filter(m => m !== modelId));
        setStatusMessage({ type: 'success', text: `${modelId} deleted successfully.` });
      } else {
        setStatusMessage({ type: 'error', text: data.message || `Failed to delete ${modelId}` });
      }
      setTimeout(() => setStatusMessage(null), 5000);
    } catch (err: any) {
      setStatusMessage({ type: 'error', text: err?.message || `Failed to delete ${modelId}` });
      setTimeout(() => setStatusMessage(null), 6000);
    } finally {
      setDeletingModel(null);
    }
  };

  // ── Provider handlers ────────────────────────────────────────
  const handleCreateProvider = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      const slug = toSlug(newProvider.name);
      const payload: Record<string, any> = {
        name:          newProvider.name,
        provider_type: newProvider.provider_type,
        slug,
        base_url:      newProvider.base_url || null,
        is_local:      isLocalProvider(newProvider.provider_type),
        auth_type:     isLocalProvider(newProvider.provider_type) ? 'none' : newProvider.auth_type,
        config:        {
          ...providerConfigBase,
          ...(newProvider.api_key ? { api_key: newProvider.api_key } : {}),
          models: configuredModels,
        },
      };

      if (editingProviderId) {
        await axios.patch(`/api/v1/model-providers/${editingProviderId}`, payload);
        setStatusMessage({ type: 'success', text: 'Model provider updated successfully.' });
      } else {
        await axios.post('/api/v1/model-providers', payload);
        setStatusMessage({ type: 'success', text: 'Model provider added successfully.' });
      }

      setNewProvider({ name: '', provider_type: 'openai', auth_type: 'api_key', api_key: '', base_url: PROVIDER_BASE_URLS['openai'], is_active: true });
      setConfiguredModels([]);
      setCustomModelInput('');
      setProviderConfigBase({});
      setEditingProviderId(null);
      setBaseUrlOverride(false);
      fetchData();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail
        : Array.isArray(detail) ? detail.map((d: any) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join(', ')
        : 'Failed to save provider.';
      setStatusMessage({ type: 'error', text: msg });
    } finally {
      setSaving(false);
      setTimeout(() => setStatusMessage(null), 5000);
    }
  };

  const handleStartEdit = (p: any) => {
    setEditingProviderId(p.id);
    setNewProvider({
      name: p.name,
      provider_type: p.provider_type,
      auth_type: p.auth_type || 'api_key',
      api_key: p.config?.api_key || '',
      base_url: p.base_url || PROVIDER_BASE_URLS[p.provider_type] || '',
      is_active: p.status === 'connected'
    });
    const models: string[] = Array.isArray(p.config?.models)
      ? p.config.models.filter((value: unknown): value is string => typeof value === 'string' && !!value.trim())
      : [p.config?.model_id, p.config?.model].filter((value: unknown): value is string => typeof value === 'string' && !!value.trim());
    setConfiguredModels([...new Set(models.map((value: string) => value.trim()))]);
    setCustomModelInput('');
    setProviderConfigBase(p.config || {});
    setBaseUrlOverride(!!p.base_url);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const handleCancelEdit = () => {
    setEditingProviderId(null);
    setNewProvider({
      name: '',
      provider_type: 'openai',
      auth_type: 'api_key',
      api_key: '',
      base_url: PROVIDER_BASE_URLS['openai'],
      is_active: true
    });
    setConfiguredModels([]);
    setCustomModelInput('');
    setProviderConfigBase({});
    setBaseUrlOverride(false);
  };

  const handleToggleProvider = async (id: string, currentStatus: string) => {
    const newStatus = currentStatus === 'connected' ? 'disabled' : 'connected';
    try {
      await axios.patch(`/api/v1/model-providers/${id}`, { status: newStatus });
      fetchData();
    } catch (error) {
      console.error('Error toggling provider:', error);
    }
  };

  const handleDeleteProvider = async (id: string, name: string) => {
    if (!confirm(`Remove provider "${name}" from the grid? This cannot be undone.`)) return;
    try {
      await axios.delete(`/api/v1/model-providers/${id}`);
      setStatusMessage({ type: 'success', text: `Provider "${name}" removed.` });
      fetchData();
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to delete provider.' });
    } finally {
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };


  // ── MCP handlers ─────────────────────────────────────────────
  const handleRegisterMcp = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegisterSaving(true);

    const payload = mcpRegisterMode === 'quick' && selectedMcp
      ? {
          name:           selectedMcp.name,
          slug:           toSlug(selectedMcp.name),
          connector_type: 'mcp',
          source:         'manual',
          base_url:       selectedMcp.transport === 'sse' ? selectedMcp.github_url : null,
          auth_type:      'custom',
          risk_level:     selectedMcp.risk_level,
          config: {
            command: selectedMcp.command,
            args: selectedMcp.args,
            env: mcpEnvValues,
            transport: selectedMcp.transport,
            npm_package: selectedMcp.npm_package
          }
        }
      : {
          name:           newMcp.name,
          slug:           toSlug(newMcp.name),
          connector_type: 'mcp',
          source:         'manual',
          base_url:       newMcp.transport === 'sse' ? newMcp.command : null,
          auth_type:      'custom',
          risk_level:     newMcp.risk_level,
          config: {
            command: newMcp.transport === 'stdio' ? newMcp.command : undefined,
            args: newMcp.transport === 'stdio' ? newMcp.args.split(' ').filter(Boolean) : undefined,
            env: mcpEnvValues,
            transport: newMcp.transport
          }
        };

    try {
      await axios.post('/api/v1/tools', payload);
      setStatusMessage({ type: 'success', text: `MCP Server "${payload.name}" registered.` });
      setShowRegisterMcp(false);
      setSelectedMcp(null);
      setMcpSearch('');
      setMcpEnvValues({});
      setNewMcp({ name: '', command: '', args: '', transport: 'stdio', risk_level: 'medium' });
      fetchData();
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to register MCP server.' });
    } finally {
      setRegisterSaving(false);
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  // ── Tool handlers ────────────────────────────────────────────
  const handleRegisterTool = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegisterSaving(true);

    // In Quick Pick mode the data comes from selectedApi; in manual from newTool
    const payload = registerMode === 'quick' && selectedApi
      ? {
          name:           selectedApi.name,
          slug:           toSlug(selectedApi.name),
          connector_type: selectedApi.connector_type,
          source:         'manual',
          base_url:       selectedApi.base_url,
          auth_type:      selectedApi.auth_type,
          risk_level:     selectedApi.risk_level,
          config:         quickApiKey ? { api_key: quickApiKey } : {},
        }
      : {
          name:           newTool.name,
          slug:           newTool.slug || toSlug(newTool.name),
          connector_type: newTool.connector_type,
          source:         'manual',
          base_url:       newTool.base_url || null,
          auth_type:      newTool.auth_type,
          risk_level:     newTool.risk_level,
          config:         {},
        };

    try {
      await axios.post('/api/v1/tools', payload);
      setStatusMessage({ type: 'success', text: `Tool "${payload.name}" registered.` });
      setShowRegisterTool(false);
      setSelectedApi(null);
      setApiSearch('');
      setQuickApiKey('');
      setNewTool({ name: '', slug: '', base_url: '', connector_type: 'api', auth_type: 'api_key', risk_level: 'low' });
      fetchData();
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to register tool.' });
    } finally {
      setRegisterSaving(false);
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  const handleDeleteTool = async (id: string, name: string) => {
    if (!confirm(`Remove tool connector "${name}"? This cannot be undone.`)) return;
    try {
      await axios.delete(`/api/v1/tools/${id}`);
      setStatusMessage({ type: 'success', text: `Tool "${name}" removed.` });
      fetchData();
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to delete tool.' });
    } finally {
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  // ── Routing profile handlers ─────────────────────────────────
  const handleCreateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newProfile.name.trim()) return;
    setProfileSaving(true);
    try {
      await axios.post('/api/v1/model-routing-profiles', {
        name: newProfile.name,
        description: newProfile.description || null,
        is_default: newProfile.is_default,
        rules: [],
      });
      setStatusMessage({ type: 'success', text: `Profile "${newProfile.name}" created.` });
      setNewProfile({ name: '', description: '', is_default: false });
      setShowCreateProfile(false);
      fetchData();
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to create routing profile.' });
    } finally {
      setProfileSaving(false);
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  const handleDeleteProfile = async (id: string, name: string) => {
    if (!confirm(`Delete routing profile "${name}"? This cannot be undone.`)) return;
    try {
      await axios.delete(`/api/v1/model-routing-profiles/${id}`);
      setStatusMessage({ type: 'success', text: `Profile "${name}" deleted.` });
      if (expandedProfileId === id) setExpandedProfileId(null);
      fetchData();
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to delete profile.' });
    } finally {
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  const handleSetDefault = async (id: string) => {
    try {
      await axios.patch(`/api/v1/model-routing-profiles/${id}`, { is_default: true });
      setStatusMessage({ type: 'success', text: 'Default routing profile updated.' });
      fetchData();
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to update default profile.' });
    } finally {
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  const handleStartEditRule = (idx: number, rule: any) => {
    setEditingRuleIdx(idx);
    setNewRule({
      task_type: rule.task_type,
      primary_model_id: rule.primary_model_id,
      fallback_model_ids: rule.fallback_model_ids || [],
      latency_bias: rule.latency_bias || '',
      cost_bias: rule.cost_bias || '',
    });
    setShowAddRule(true);
  };

  const handleAddRule = async (profileId: string, existingRules: any[]) => {
    if (!newRule.primary_model_id) return;
    const rule = {
      task_type: newRule.task_type,
      primary_model_id: newRule.primary_model_id,
      fallback_model_ids: newRule.fallback_model_ids,
      latency_bias: newRule.latency_bias || null,
      cost_bias: newRule.cost_bias || null,
    };

    let updatedRules: any[];
    if (editingRuleIdx !== null) {
      updatedRules = [...existingRules];
      updatedRules[editingRuleIdx] = rule;
    } else {
      updatedRules = [...existingRules, rule];
    }

    try {
      await axios.patch(`/api/v1/model-routing-profiles/${profileId}`, {
        rules: updatedRules,
      });
      setStatusMessage({ type: 'success', text: editingRuleIdx !== null ? 'Routing rule updated.' : 'Routing rule added.' });
      setShowAddRule(false);
      setEditingRuleIdx(null);
      setNewRule({ task_type: '*', primary_model_id: '', fallback_model_ids: [], latency_bias: '', cost_bias: '' });
      fetchData();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setStatusMessage({ 
        type: 'error', 
        text: detail ? `Save failed: ${detail}` : 'Failed to save rule. Please try a hard refresh (Ctrl+F5).' 
      });
    } finally {
      setTimeout(() => setStatusMessage(null), 5000);
    }
  };

  const handleDeleteRule = async (profileId: string, existingRules: any[], ruleIdx: number) => {
    const updated = existingRules.filter((_, i) => i !== ruleIdx);
    try {
      await axios.patch(`/api/v1/model-routing-profiles/${profileId}`, { rules: updated });
      setStatusMessage({ type: 'success', text: 'Rule removed successfully.' });
      fetchData();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setStatusMessage({ 
        type: 'error', 
        text: detail ? `Delete failed: ${detail}` : 'Failed to remove rule. Check backend logs or try a hard refresh.' 
      });
    } finally {
      setTimeout(() => setStatusMessage(null), 5000);
    }
  };

  // ── Quick Pick filtered list ─────────────────────────────────
  const filteredApis = useMemo(() => {
    if (!apiSearch.trim()) return PUBLIC_APIS;
    const q = apiSearch.toLowerCase();
    return PUBLIC_APIS.filter(a =>
      a.name.toLowerCase().includes(q) || a.description.toLowerCase().includes(q)
    );
  }, [apiSearch]);

  // ── Provider helpers ─────────────────────────────────────────
  const getProviderColor = (type: string) => {
    switch (type) {
      case 'openai':     return { bg: 'bg-green-500/10',         text: 'text-green-500' };
      case 'anthropic':  return { bg: 'bg-shogun-gold/10',        text: 'text-shogun-gold' };
      case 'google':     return { bg: 'bg-blue-400/10',           text: 'text-blue-400' };
      case 'openrouter': return { bg: 'bg-purple-400/10',         text: 'text-purple-400' };
      case 'ollama':     return { bg: 'bg-cyan-400/10',           text: 'text-cyan-400' };
      case 'lmstudio':   return { bg: 'bg-orange-400/10',         text: 'text-orange-400' };
      default:           return { bg: 'bg-shogun-blue/10',        text: 'text-shogun-blue' };
    }
  };

  const getProviderDisplayType = (type: string) => {
    const map: Record<string, string> = {
      openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google Gemini',
      openrouter: 'OpenRouter', ollama: 'Ollama', lmstudio: 'LM Studio',
      local: 'Local', custom: 'Custom',
    };
    return map[type] || type;
  };

  const currentDocLink = PROVIDER_DOCS[newProvider.provider_type];
  const isLocal        = isLocalProvider(newProvider.provider_type);

  return (
    <div className="space-y-6 animate-in fade-in duration-500 max-w-6xl mx-auto pb-12">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-3xl font-bold shogun-title flex items-center gap-3">
            {t('katana.title', 'The Katana')} <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">{t('katana.badge')}</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">{t('katana.subtitle', 'Manage the cutting-edge models and tools that empower your agents.')}</p>
        </div>
        <button
          type="button"
          onClick={() => navigate('/toolgate')}
          className="flex items-center gap-2 self-start rounded-lg border border-orange-400/25 bg-orange-500/[0.07] px-3 py-2.5 text-xs font-bold text-orange-300 transition-colors hover:bg-orange-500/15"
        >
          <Shield className="h-4 w-4" />
          Configure runtime rules in ToolGate
        </button>
      </div>

      {/* ── Status toast ───────────────────────────────────────── */}
      {statusMessage && (
        <div className={cn(
          "p-3 rounded-lg flex items-center gap-3 animate-in slide-in-from-top-2",
          statusMessage.type === 'success'
            ? "bg-green-500/10 text-green-500 border border-green-500/20"
            : "bg-red-500/10 text-red-500 border border-red-500/20"
        )}>
          {statusMessage.type === 'success' ? <CheckCircle2 className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
          <span className="text-sm font-medium">{statusMessage.text}</span>
        </div>
      )}

      {/* ── Tab bar ────────────────────────────────────────────── */}
      <div className="flex border-b border-shogun-border overflow-x-auto">
        {(['providers', 'tools', 'files', 'routing', 'skills', 'team', 'telegram', 'teams', 'mail_calendar', 'office', 'ide', 'mado', 'ronin', 'skillopt'] as TabType[]).filter(tab => tab !== 'ide' || ['campaign', 'ronin'].includes(officePosture)).map((tab) => (
          <button
            key={tab}
            onClick={() => {
              setActiveTab(tab);
              if (tab === 'telegram' && !tgStatus) fetchTgStatus();
              if (tab === 'mail_calendar' && !mailAccount) fetchMailStatus();
              if (tab === 'office' && !officeStatus) fetchOfficeData();
            }}
            className={cn(
              "px-6 py-3 text-[10px] font-bold uppercase tracking-widest transition-all relative",
              activeTab === tab ? "text-shogun-blue" : "text-shogun-subdued hover:text-shogun-text"
            )}
          >
            {tab === 'providers' && t('katana.tab_cloud', 'AI Model Provider')}
            {tab === 'tools'     && t('katana.tab_tools', 'Toolbox & APIs')}
            {tab === 'files'     && <span className="flex items-center gap-1.5"><FileText className="w-3.5 h-3.5" />File Formats</span>}
            {tab === 'routing'   && t('katana.tab_routing', 'Logic Routing')}
            {tab === 'team'      && <span className="flex items-center gap-1.5"><Users className="w-3.5 h-3.5" />{t('katana.team.tab', 'Team')}</span>}
            {tab === 'skills'    && <span className="flex items-center gap-1.5"><Puzzle className="w-3.5 h-3.5" />Skills · Active Usage</span>}
            {tab === 'telegram'  && (
              <span className="flex items-center gap-1.5">
                <MessageCircle className="w-3.5 h-3.5" />
                Telegram
                {tgStatus?.connected && (
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
                )}
              </span>
            )}
            {tab === 'teams' && (
              <span className="flex items-center gap-1.5">
                <MessageCircle className="w-3.5 h-3.5" />
                Microsoft Teams
              </span>
            )}
            {tab === 'mail_calendar' && (
              <span className="flex items-center gap-1.5">
                <Mail className="w-3.5 h-3.5" />
                Mail & Calendar
                {mailAccount?.is_active && (
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
                )}
              </span>
            )}
            {tab === 'office' && (
              <span className={cn("flex items-center gap-1.5", officePosture === 'shrine' && "opacity-40")}>
                <FileSpreadsheet className="w-3.5 h-3.5" />
                Office
                {officeStatus?.enabled && officePosture !== 'shrine' && (
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
                )}
              </span>
            )}
            {tab === 'ide' && (
              <span className="flex items-center gap-1.5"><Monitor className="w-3.5 h-3.5" /> IDE Mode</span>
            )}
            {tab === 'mado'      && (
              <span className="flex items-center gap-1.5">
                <AppWindow className="w-3.5 h-3.5" />
                Mado Browser
              </span>
            )}
            {tab === 'ronin'     && (
              <span className="flex items-center gap-1.5">
                <Crosshair className="w-3.5 h-3.5" />
                Ronin Desktop
              </span>
            )}
            {tab === 'skillopt' && (
              <span className="flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5" />
                {t('katana.tab_skillopt', 'SkillOpt')}
              </span>
            )}
            {activeTab === tab && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-shogun-blue shadow-[0_0_10px_rgba(74,140,199,0.5)]" />
            )}
          </button>
        ))}
      </div>

      <div className="mt-6">
        {/* ════════════════════════════════════════════════════════
            PROVIDERS TAB
        ════════════════════════════════════════════════════════ */}
        {activeTab === 'skills' && <ActiveSkillsPanel />}
        {activeTab === 'files' && <FileFormatsPanel />}
        {activeTab === 'team' && <TeamMembersPanel />}

        {activeTab === 'providers' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Add Provider form */}
            <div className="lg:col-span-1">
              <div className="shogun-card space-y-6 sticky top-6">
                <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                  {editingProviderId ? (
                    <><Edit2 className="w-5 h-5 text-shogun-gold" /> {t('common.edit', 'Edit Provider')}</>
                  ) : (
                    <><Plus className="w-5 h-5 text-shogun-blue" /> {t('katana.add_provider', 'Add Provider')}</>
                  )}
                </h3>
                <form onSubmit={handleCreateProvider} className="space-y-4">
                  {/* Provider selector */}
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.provider', 'Provider')}</label>
                    <select
                      value={newProvider.provider_type}
                      onChange={(e) => {
                        const type = e.target.value;
                        setNewProvider({
                          ...newProvider,
                          provider_type: type,
                          name: '',
                          base_url: PROVIDER_BASE_URLS[type] || '',
                        });
                        setConfiguredModels([]);
                        setCustomModelInput('');
                        setProviderConfigBase({});
                        setBaseUrlOverride(false);
                      }}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                    >
                      <optgroup label={t('katana.ai_model_providers')}>
                        <option value="openai">OpenAI</option>
                        <option value="google">Google (Gemini)</option>
                        <option value="anthropic">Anthropic</option>
                        <option value="openrouter">OpenRouter</option>
                      </optgroup>
                      <optgroup label={t('katana.local_providers')}>
                        <option value="ollama">Ollama (Local)</option>
                        <option value="lmstudio">LM Studio (Local)</option>
                      </optgroup>
                    </select>
                  </div>

                  {/* Doc link */}
                  {currentDocLink && (
                    <a
                      href={currentDocLink.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-2 p-2.5 rounded-lg bg-shogun-blue/5 border border-shogun-blue/15 text-shogun-blue hover:bg-shogun-blue/10 hover:border-shogun-blue/30 transition-all group"
                    >
                      <Link2 className="w-3.5 h-3.5 shrink-0" />
                      <span className="text-[11px] font-semibold truncate">{currentDocLink.label}</span>
                      <ExternalLink className="w-3 h-3 ml-auto opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
                    </a>
                  )}

                  {/* Display Name / Local model picker */}
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">
                      {isLocal ? t('katana.available_models') : t('katana.display_name')}
                    </label>
                    {isLocal && localModels.length > 0 ? (
                      <select
                        required
                        value={newProvider.name}
                        onChange={(e) => setNewProvider({...newProvider, name: e.target.value})}
                        className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                      >
                        <option value="" disabled>{t('katana.select_pulled_model')}</option>
                        {localModels.map((m) => (
                          <option key={m} value={m}>{m}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type="text"
                        required
                        placeholder={isLocal ? "e.g. llama3:8b (or connect to fetch)" : "e.g. Primary OpenAI"}
                        value={newProvider.name}
                        onChange={(e) => setNewProvider({...newProvider, name: e.target.value})}
                        className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                      />
                    )}
                    {isLocal && localModels.length === 0 && (
                      <div className="flex items-center gap-2 mt-1">
                        <button
                          type="button"
                          onClick={() => fetchLocalModels(newProvider.provider_type)}
                          className="text-[9px] font-bold text-shogun-blue hover:text-shogun-gold uppercase tracking-widest transition-colors flex items-center gap-1"
                        >
                          <RefreshCw className="w-2.5 h-2.5" /> {t('katana.scan_for_local_models')}
                        </button>
                        <span className="text-[9px] text-shogun-subdued">• Ensure {newProvider.provider_type === 'ollama' ? 'Ollama' : 'LM Studio'} is running</span>
                      </div>
                    )}
                  </div>

                  <div className="space-y-2.5 pt-2 border-t border-shogun-border/40">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center justify-between">
                      <span>Active Models ({configuredModels.length})</span>
                      <span className="text-[8px] text-purple-400 font-semibold normal-case">Router candidates</span>
                    </label>
                    <div className="flex flex-wrap gap-1.5 min-h-[36px] p-2 bg-[#050508] border border-shogun-border rounded-lg">
                      {configuredModels.map((modelId) => (
                        <span key={modelId} className="inline-flex items-center gap-1 text-[10px] font-mono px-2 py-0.5 rounded bg-purple-500/15 border border-purple-500/30 text-purple-300 font-semibold">
                          {modelId}
                          <button
                            type="button"
                            onClick={() => setConfiguredModels(current => current.filter(item => item !== modelId))}
                            className="text-purple-400 hover:text-red-400 font-bold ml-0.5"
                            aria-label={`Remove ${modelId}`}
                          >
                            ×
                          </button>
                        </span>
                      ))}
                      {configuredModels.length === 0 && (
                        <span className="text-[10px] text-shogun-subdued italic py-0.5">No models selected. This provider will not be used for routing.</span>
                      )}
                    </div>

                    {!!PROVIDER_MODEL_PRESETS[newProvider.provider_type]?.length && (
                      <div className="space-y-1">
                        <span className="text-[9px] text-shogun-subdued font-medium">Quick add:</span>
                        <div className="flex flex-wrap gap-1">
                          {PROVIDER_MODEL_PRESETS[newProvider.provider_type].map((preset) => {
                            const selected = configuredModels.includes(preset);
                            return (
                              <button
                                key={preset}
                                type="button"
                                onClick={() => setConfiguredModels(current => selected
                                  ? current.filter(modelId => modelId !== preset)
                                  : [...current, preset])}
                                className={cn(
                                  "text-[9px] font-mono px-2 py-0.5 rounded border transition-all",
                                  selected
                                    ? "bg-purple-500/20 border-purple-400 text-purple-300 font-bold"
                                    : "bg-[#050508] border-shogun-border text-shogun-subdued hover:border-purple-400/40 hover:text-shogun-text"
                                )}
                              >
                                {selected ? `✓ ${preset}` : `+ ${preset}`}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    <div className="flex gap-1.5 pt-1">
                      <input
                        type="text"
                        placeholder="Exact model ID"
                        value={customModelInput}
                        onChange={(event) => setCustomModelInput(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key !== 'Enter' || !customModelInput.trim()) return;
                          event.preventDefault();
                          const modelId = customModelInput.trim();
                          setConfiguredModels(current => current.includes(modelId) ? current : [...current, modelId]);
                          setCustomModelInput('');
                        }}
                        className="flex-1 bg-[#050508] border border-shogun-border rounded-lg px-2.5 py-1.5 text-xs font-mono focus:border-purple-400 outline-none"
                      />
                      <button
                        type="button"
                        disabled={!customModelInput.trim()}
                        onClick={() => {
                          const modelId = customModelInput.trim();
                          if (modelId) setConfiguredModels(current => current.includes(modelId) ? current : [...current, modelId]);
                          setCustomModelInput('');
                        }}
                        className="px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600/30 border border-purple-500/40 text-purple-300 text-[10px] font-bold uppercase rounded-lg disabled:opacity-40"
                      >
                        Add
                      </button>
                    </div>
                  </div>

                  {/* Auth Configuration (cloud only) */}
                  {!isLocal && (
                    <>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.auth_type', 'Auth Type')}</label>
                        <select
                          value={newProvider.auth_type}
                          onChange={(e) => setNewProvider({...newProvider, auth_type: e.target.value})}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                        >
                          <option value="api_key">{t('katana.api_key_option')}</option>
                          <option value="oauth">{t('katana.oauth_option')}</option>
                        </select>
                      </div>
                      <div className="space-y-1.5 mt-3">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">
                          {newProvider.auth_type === 'oauth' ? t('katana.oauth_token') : t('katana.api_key_label')}
                        </label>
                        <input
                          type="password"
                          placeholder={newProvider.auth_type === 'oauth' ? 'Bearer ...' : 'sk-...'}
                          value={newProvider.api_key}
                          onChange={(e) => setNewProvider({...newProvider, api_key: e.target.value})}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                        />
                      </div>
                    </>
                  )}

                  {/* Base URL — pre-filled, editable on override */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">
                        {t('katana.base_url_label')} {isLocal ? '' : t('katana.auto')}
                      </label>
                      <button
                        type="button"
                        onClick={() => setBaseUrlOverride(v => !v)}
                        className={cn(
                          "text-[9px] font-bold uppercase tracking-widest transition-colors",
                          baseUrlOverride ? "text-shogun-gold" : "text-shogun-blue hover:text-shogun-gold"
                        )}
                      >
                        {baseUrlOverride ? t('katana.reset') : t('katana.override')}
                      </button>
                    </div>
                    <div className="relative">
                      <input
                        type="text"
                        readOnly={!baseUrlOverride}
                        placeholder={PROVIDER_BASE_URLS[newProvider.provider_type] || 'https://...'}
                        value={newProvider.base_url}
                        onChange={(e) => setNewProvider({...newProvider, base_url: e.target.value})}
                        className={cn(
                          "w-full bg-[#050508] border rounded-lg p-3 text-sm outline-none font-mono text-xs transition-all",
                          baseUrlOverride
                            ? "border-shogun-gold text-shogun-gold focus:ring-1 focus:ring-shogun-gold/20 cursor-text"
                            : "border-shogun-border text-shogun-subdued cursor-default select-none"
                        )}
                      />
                      {!baseUrlOverride && (
                        <div className="absolute right-3 top-1/2 -translate-y-1/2">
                          <span className="text-[8px] text-green-400 font-bold uppercase border border-green-400/20 bg-green-400/5 px-1.5 py-0.5 rounded">
                            {t('katana.default')}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Model Location — local providers only */}
                  {isLocal && (
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-1.5">
                        <Folder className="w-3 h-3" /> {t('katana.model_location')}
                        <span className="text-shogun-subdued/50 normal-case font-normal tracking-normal text-[9px]">({t('katana.filesystem_path')})</span>
                      </label>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          placeholder={
                            newProvider.provider_type === 'ollama'
                              ? 'C:\\Users\\you\\.ollama\\models'
                              : 'C:\\Users\\you\\AppData\\Local\\LM Studio\\models'
                          }
                          value={localModelPath}
                          onChange={(e) => setLocalModelPath(e.target.value)}
                          className="flex-1 bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue outline-none font-mono text-xs"
                        />
                        <button
                          type="button"
                          disabled={scanningModels || !localModelPath.trim()}
                          onClick={handleScanLocalModels}
                          className="flex items-center gap-1.5 px-3 py-2 bg-shogun-blue/10 hover:bg-shogun-blue/20 border border-shogun-blue/30 hover:border-shogun-blue/60 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg text-shogun-blue text-[10px] font-bold uppercase tracking-widest transition-all whitespace-nowrap"
                        >
                          {scanningModels
                            ? <RefreshCw className="w-3 h-3 animate-spin" />
                            : <Search className="w-3 h-3" />}
                          Scan
                        </button>
                      </div>
                      <p className="text-[9px] text-shogun-subdued leading-relaxed">
                        Paste the path shown in your {newProvider.provider_type === 'ollama' ? 'Ollama' : 'LM Studio'} settings.
                        The backend will walk the directory and return every pulled model.
                      </p>
                    </div>
                  )}

                  {/* {t('katana.pull_model')} — Ollama only */}
                  {newProvider.provider_type === 'ollama' && (
                    <div className="border border-shogun-border rounded-xl overflow-hidden">
                      <button
                        type="button"
                        onClick={() => setShowPullPanel(p => !p)}
                        className="w-full flex items-center justify-between px-4 py-3 bg-[#050508] hover:bg-[#0a0e1a] transition-colors"
                      >
                        <span className="flex items-center gap-2 text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">
                          <Download className="w-3.5 h-3.5 text-cyan-400" />
                          Pull a Model
                          <span className="text-cyan-400/60 normal-case font-normal tracking-normal">
                            — {t('katana.download_to_ollama')}
                          </span>
                        </span>
                        {showPullPanel
                          ? <ChevronUp className="w-3.5 h-3.5 text-shogun-subdued" />
                          : <ChevronDown className="w-3.5 h-3.5 text-shogun-subdued" />}
                      </button>

                      {showPullPanel && (
                        <div className="p-4 space-y-4 border-t border-shogun-border bg-[#02040a]">
                          {/* Live progress bar */}
                          {pullingModel && pullStatus && (
                            <div className="p-3 rounded-xl bg-cyan-500/5 border border-cyan-500/20 space-y-2">
                              <div className="flex items-center justify-between">
                                <span className="text-[10px] font-bold text-cyan-400 uppercase tracking-widest truncate">
                                  ↓ {pullingModel}
                                </span>
                                <span className="text-[10px] font-mono text-cyan-400/70 ml-2 shrink-0">
                                  {pullStatus.percent}%
                                </span>
                              </div>
                              <div className="w-full h-1.5 bg-[#0a0e1a] rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-gradient-to-r from-cyan-500 to-shogun-blue rounded-full transition-all duration-300"
                                  style={{ width: `${pullStatus.percent}%` }}
                                />
                              </div>
                              <p className="text-[9px] text-cyan-400/60 font-mono truncate">{pullStatus.status}</p>
                            </div>
                          )}

                          {/* Search input */}
                          <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-shogun-subdued/50" />
                            <input
                              type="text"
                              value={ollamaQuery}
                              onChange={e => setOllamaQuery(e.target.value)}
                              placeholder="Search all Ollama models..."
                              className="w-full bg-[#050508] border border-shogun-border rounded-lg pl-9 pr-3 py-2 text-xs focus:border-cyan-500/60 outline-none placeholder:text-shogun-subdued/40"
                            />
                            {ollamaLoading && (
                              <RefreshCw className="absolute right-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-cyan-400 animate-spin" />
                            )}
                          </div>

                          {/* Category filter */}
                          <div className="flex gap-1 flex-wrap">
                            {(['all', 'vision', 'tools', 'thinking', 'embedding', 'cloud'] as const).map(f => (
                              <button
                                key={f}
                                type="button"
                                onClick={() => setPullCatalogFilter(f)}
                                className={cn(
                                  "px-2.5 py-1 rounded text-[9px] font-bold uppercase tracking-widest border transition-all",
                                  pullCatalogFilter === f
                                    ? "bg-cyan-500/15 border-cyan-500/40 text-cyan-400"
                                    : "bg-transparent border-shogun-border text-shogun-subdued hover:border-shogun-subdued"
                                )}
                              >
                                {f}
                              </button>
                            ))}
                          </div>

                          {/* Model results */}
                          <div className="grid grid-cols-1 gap-2 max-h-80 overflow-y-auto pr-1 scrollbar-thin">
                            {ollamaLoading && ollamaResults.length === 0 ? (
                              <div className="flex items-center justify-center py-8 text-shogun-subdued/50">
                                <RefreshCw className="w-4 h-4 animate-spin mr-2" />
                                <span className="text-[10px]">Searching ollama.com...</span>
                              </div>
                            ) : ollamaResults.length === 0 ? (
                              <div className="flex flex-col items-center justify-center py-8 text-shogun-subdued/50">
                                <span className="text-[10px]">No models found</span>
                                <span className="text-[9px] mt-1">Try a different search or use a custom tag below</span>
                              </div>
                            ) : (
                              ollamaResults.map(m => {
                                const isThis = pullingModel === m.id;
                                const matchingLocalModel = localModels.find(model => {
                                  const normModel = model.toLowerCase();
                                  const normId = m.id.toLowerCase();
                                  if (normModel === normId) return true;
                                  if (normModel.startsWith(normId + ':')) return true;
                                  return false;
                                });
                                const alreadyHave = !!matchingLocalModel;
                                return (
                                  <div
                                    key={m.id}
                                    className={cn(
                                      "flex items-center justify-between p-2.5 rounded-lg border transition-all",
                                      isThis
                                        ? "border-cyan-500/40 bg-cyan-500/5"
                                        : alreadyHave
                                          ? "border-green-500/20 bg-green-500/5"
                                          : "border-shogun-border hover:border-shogun-subdued bg-[#050508]"
                                    )}
                                  >
                                    <div className="min-w-0">
                                      <div className="flex items-center gap-2 flex-wrap">
                                        <span className="text-[10px] font-bold text-shogun-text truncate">{m.name}</span>
                                        {m.sizes.map(s => (
                                          <span key={s} className="text-[7px] px-1 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-blue-400 font-bold shrink-0">{s}</span>
                                        ))}
                                        {alreadyHave && <span className="text-[8px] text-green-400 font-bold shrink-0">✓ local</span>}
                                      </div>
                                      <p className="text-[8px] text-shogun-subdued/70 truncate mt-0.5">{m.description}</p>
                                      <div className="flex items-center gap-2 mt-0.5">
                                        {m.capabilities.map(cap => (
                                          <span key={cap} className="text-[7px] px-1 py-0.5 rounded bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 font-medium">{cap}</span>
                                        ))}
                                        <span className="text-[7px] text-shogun-subdued/50 font-mono">↓{m.pulls}</span>
                                        {m.tag_count > 0 && <span className="text-[7px] text-shogun-subdued/50 font-mono">{m.tag_count} tags</span>}
                                        {m.updated && <span className="text-[7px] text-shogun-subdued/40">{m.updated}</span>}
                                      </div>
                                    </div>
                                    <div className="ml-3 shrink-0 flex items-center gap-1">
                                      <button
                                        type="button"
                                        disabled={!!pullingModel}
                                        onClick={() => handlePullModel(m.id)}
                                        className={cn(
                                          "flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[9px] font-bold uppercase transition-all border",
                                          isThis
                                            ? "border-cyan-500/40 text-cyan-400 bg-cyan-500/10 animate-pulse"
                                            : alreadyHave
                                              ? "border-green-500/20 text-green-400 bg-green-500/5 hover:bg-green-500/10"
                                              : "border-shogun-border text-shogun-subdued hover:border-cyan-500/50 hover:text-cyan-400 hover:bg-cyan-500/5 disabled:opacity-30 disabled:cursor-not-allowed"
                                        )}
                                      >
                                        {isThis
                                          ? <><RefreshCw className="w-2.5 h-2.5 animate-spin" /> {t('katana.pulling')}</>
                                          : alreadyHave
                                            ? <><RefreshCw className="w-2.5 h-2.5" /> {t('katana.repull')}</>
                                            : <><Download className="w-2.5 h-2.5" /> {t('katana.pull')}</>}
                                      </button>
                                      {alreadyHave && matchingLocalModel && localProviderType === 'ollama' && (
                                        <button
                                          type="button"
                                          disabled={!!pullingModel || deletingModel === matchingLocalModel}
                                          onClick={(e) => { e.stopPropagation(); handleDeleteOllamaModel(matchingLocalModel); }}
                                          className={cn(
                                            "p-1.5 rounded-lg transition-all border",
                                            deletingModel === matchingLocalModel
                                              ? "border-red-500/40 text-red-400 bg-red-500/10 animate-pulse"
                                              : "border-shogun-border text-red-500/40 hover:border-red-500/50 hover:text-red-500 hover:bg-red-500/5 disabled:opacity-30 disabled:cursor-not-allowed"
                                          )}
                                          title={t('katana.delete_local_model', 'Delete from Ollama')}
                                        >
                                          <Trash2 className="w-3 h-3" />
                                        </button>
                                      )}
                                    </div>
                                  </div>
                                );
                              })
                            )}

                            {/* Load More */}
                            {ollamaHasMore && !ollamaLoading && (
                              <button
                                type="button"
                                onClick={() => searchOllamaModels(ollamaQuery, ollamaPage + 1, true)}
                                disabled={ollamaLoadingMore}
                                className="w-full py-2 rounded-lg border border-shogun-border text-[9px] font-bold uppercase tracking-widest text-shogun-subdued hover:border-cyan-500/40 hover:text-cyan-400 transition-all disabled:opacity-50"
                              >
                                {ollamaLoadingMore
                                  ? <><RefreshCw className="w-3 h-3 animate-spin inline mr-1" /> Loading...</>
                                  : 'Load More Models'}
                              </button>
                            )}
                          </div>

                          {/* Custom model tag */}
                          <div className="pt-2 border-t border-shogun-border/50 space-y-1.5">
                            <label className="text-[9px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.custom_model_tag', 'Custom Model Tag')}</label>
                            <div className="flex gap-2">
                              <input
                                type="text"
                                value={customPullTag}
                                onChange={e => setCustomPullTag(e.target.value)}
                                onKeyDown={e => { if (e.key === 'Enter' && customPullTag.trim()) { e.preventDefault(); handlePullModel(customPullTag.trim()); setCustomPullTag(''); }}}
                                placeholder="e.g. llama3.2:latest or mistral:7b-instruct"
                                className="flex-1 bg-[#050508] border border-shogun-border rounded-lg px-3 py-2 text-xs font-mono focus:border-cyan-500/60 outline-none placeholder:text-shogun-subdued/40"
                              />
                              <button
                                type="button"
                                disabled={!!pullingModel || !customPullTag.trim()}
                                onClick={() => { handlePullModel(customPullTag.trim()); setCustomPullTag(''); }}
                                className="px-3 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 hover:border-cyan-500/60 disabled:opacity-30 disabled:cursor-not-allowed rounded-lg text-cyan-400 text-[10px] font-bold uppercase tracking-widest transition-all whitespace-nowrap flex items-center gap-1"
                              >
                                <Download className="w-3 h-3" /> {t('katana.pull')}
                              </button>
                            </div>
                            <p className="text-[9px] text-shogun-subdued/60">Any valid Ollama model tag from <a href="https://ollama.com/search" target="_blank" rel="noopener noreferrer" className="text-cyan-400/70 font-mono hover:text-cyan-400 transition-colors">ollama.com/search</a></p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ── Manage Local Models ─────────────────────── */}
                  {isLocal && localModels.length > 0 && (
                    <div className="space-y-2">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-2">
                        <Monitor className="w-3.5 h-3.5" />
                        {t('katana.manage_local_models', 'Manage Local Models')}
                        <span className="text-[8px] px-1.5 py-0.5 rounded bg-[#050508] border border-shogun-border text-shogun-subdued font-bold">{localModels.length}</span>
                      </label>
                      <div className="grid grid-cols-1 gap-1.5 max-h-48 overflow-y-auto pr-1 scrollbar-thin">
                        {localModels.map(m => (
                          <div
                            key={m}
                            className="flex items-center justify-between p-2 rounded-lg border border-shogun-border bg-[#050508] hover:border-shogun-subdued transition-all"
                          >
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="w-1.5 h-1.5 rounded-full bg-green-500 shrink-0" />
                              <span className="text-[10px] font-mono text-shogun-text truncate">{m}</span>
                            </div>
                            {localProviderType === 'ollama' && (
                              <button
                                type="button"
                                disabled={deletingModel === m}
                                onClick={() => handleDeleteOllamaModel(m)}
                                className={cn(
                                  "shrink-0 flex items-center gap-1 px-2 py-1 rounded-lg text-[9px] font-bold uppercase transition-all border",
                                  deletingModel === m
                                    ? "border-red-500/40 text-red-400 bg-red-500/10 animate-pulse"
                                    : "border-shogun-border text-red-500/50 hover:border-red-500/50 hover:text-red-500 hover:bg-red-500/5"
                                )}
                                title={t('katana.delete_local_model', 'Delete from Ollama')}
                              >
                                <Trash2 className="w-3 h-3" />
                                <span>{t('katana.delete', 'Delete')}</span>
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="flex gap-2">
                    <button
                      type="submit"
                      disabled={saving || !newProvider.name}
                      className="flex-1 py-3 bg-shogun-blue hover:bg-shogun-blue/90 text-white font-bold rounded-lg shadow-shogun transition-all flex items-center justify-center gap-2"
                    >
                      {saving ? (
                        <RefreshCw className="w-4 h-4 animate-spin" />
                      ) : (
                        editingProviderId ? <CheckCircle2 className="w-4 h-4" /> : <Save className="w-4 h-4" />
                      )}
                      {editingProviderId ? t('katana.update_provider') : t('katana.initiate_provider')}
                    </button>
                    {editingProviderId && (
                      <button
                        type="button"
                        onClick={handleCancelEdit}
                        className="px-4 py-2 bg-shogun-subdued/10 hover:bg-shogun-subdued/20 border border-shogun-border rounded-lg text-shogun-subdued text-xs font-bold uppercase transition-all"
                      >
                        {t('common.cancel')}
                      </button>
                    )}
                  </div>
                </form>
              </div>
            </div>

            {/* Active Providers grid */}
            <div className="lg:col-span-2 space-y-6">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <Cpu className="w-5 h-5 text-shogun-blue" /> {t('katana.active_providers')}
              </h3>

              {loading ? (
                <div className="p-12 text-center shogun-card opacity-50">
                  <RefreshCw className="w-8 h-8 animate-spin mx-auto text-shogun-blue mb-4" />
                  <p className="text-xs uppercase tracking-widest font-bold">{t('katana.querying_model_grid')}</p>
                </div>
              ) : providers.length === 0 ? (
                <div className="p-12 text-center shogun-card border-dashed">
                  <p className="text-shogun-subdued italic">{t('katana.no_providers')}</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4">
                  {providers.map((p) => {
                    const color   = getProviderColor(p.provider_type);
                    const docLink = PROVIDER_DOCS[p.provider_type];
                    const isActive = p.status === 'connected';
                    const isLocalProv = isLocalProvider(p.provider_type);
                    return (
                      <div key={p.id} className="shogun-card group hover:border-shogun-blue/50 transition-all">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center", color.bg, color.text)}>
                              {isLocalProv
                                ? <Monitor className="w-6 h-6" />
                                : <Cloud className="w-6 h-6" />
                              }
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <h4 className="font-bold text-shogun-text">{p.name}</h4>
                                {isActive
                                  ? <span className="text-[8px] bg-green-500/10 text-green-500 px-1.5 py-0.5 rounded border border-green-500/20 font-bold uppercase">{t('katana.active')}</span>
                                  : <span className="text-[8px] bg-shogun-subdued/10 text-shogun-subdued px-1.5 py-0.5 rounded border border-shogun-border font-bold uppercase">{p.status ?? t('katana.not_configured')}</span>
                                }
                              </div>
                              <div className="flex items-center gap-2 mt-1">
                                <span className="text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded bg-[#050508] border border-shogun-border text-shogun-subdued">
                                  {getProviderDisplayType(p.provider_type)}
                                </span>
                                <span className="text-xs text-shogun-subdued">{p.base_url || t('katana.default_endpoint')}</span>
                              </div>
                              {Array.isArray(p.config?.models) && p.config.models.length > 0 && (
                                <div className="flex flex-wrap gap-1 mt-2">
                                  {p.config.models.map((modelId: string) => (
                                    <span key={modelId} className="text-[9px] font-mono px-2 py-0.5 rounded bg-purple-500/10 border border-purple-500/25 text-purple-300 font-semibold">
                                      {modelId}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            {docLink && (
                              <a
                                href={docLink.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="p-2 hover:bg-shogun-blue/10 text-shogun-subdued hover:text-shogun-blue rounded-lg transition-colors"
                                title={docLink.label}
                              >
                                <ExternalLink className="w-4 h-4" />
                              </a>
                            )}
                            <button
                              onClick={() => handleStartEdit(p)}
                              className="p-2 hover:bg-shogun-card rounded-lg transition-colors text-shogun-subdued hover:text-shogun-gold"
                              title={t('katana.edit_provider')}
                            >
                              <Edit2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => handleToggleProvider(p.id, p.status)}
                              className="p-2 hover:bg-shogun-card rounded-lg transition-colors text-shogun-subdued hover:text-shogun-text"
                              title={isActive ? t('katana.disable') : t('katana.enable')}
                            >
                              {isActive ? <Zap className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4" />}
                            </button>
                            <button
                              onClick={() => handleDeleteProvider(p.id, p.name)}
                              className="p-2 hover:bg-red-500/10 text-red-500/50 hover:text-red-500 rounded-lg transition-colors"
                              title={t('katana.delete_provider')}
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Local Models Manager */}
              {localModels.length > 0 && (
                <div className="shogun-card space-y-4 border border-shogun-border bg-[#02040a]/40 backdrop-blur-md rounded-xl p-5 mt-6">
                  <div className="flex items-center justify-between border-b border-shogun-border/40 pb-3">
                    <div className="flex items-center gap-2">
                      <Monitor className="w-5 h-5 text-green-400" />
                      <div>
                        <h4 className="font-bold text-shogun-text text-sm">Local Models Manager</h4>
                        <p className="text-[10px] text-shogun-subdued mt-0.5">Manage models pulled on your local machines</p>
                      </div>
                    </div>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-[#050508] border border-shogun-border text-green-400 font-mono font-bold">
                      {localModels.length} models
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-80 overflow-y-auto pr-1 scrollbar-thin">
                    {localModels.map(m => {
                      return (
                        <div
                          key={m}
                          className="flex items-center justify-between p-3 rounded-lg border border-shogun-border bg-[#050508]/60 hover:border-shogun-subdued transition-all group"
                        >
                          <div className="flex flex-col min-w-0 mr-3">
                            <div className="flex items-center gap-2 min-w-0">
                              <span className="w-2 h-2 rounded-full bg-green-500 shrink-0 shadow-[0_0_8px_#22c55e]" />
                              <span className="text-xs font-mono text-shogun-text truncate font-semibold" title={m}>{m}</span>
                            </div>
                          </div>
                          {localProviderType === 'ollama' && (
                            <button
                              type="button"
                              disabled={deletingModel === m}
                              onClick={() => handleDeleteOllamaModel(m)}
                              className={cn(
                                "shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[9px] font-bold uppercase transition-all border",
                                deletingModel === m
                                  ? "border-red-500/40 text-red-400 bg-red-500/10 animate-pulse"
                                  : "border-shogun-border text-red-500/60 hover:border-red-500 hover:text-red-500 hover:bg-red-500/10"
                              )}
                              title={t('katana.delete_local_model', 'Delete from Ollama')}
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                              <span>{deletingModel === m ? t('katana.deleting', 'Deleting') : t('katana.delete', 'Delete')}</span>
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════════════════════
            TOOLS TAB
        ════════════════════════════════════════════════════════ */}
        {activeTab === 'tools' && (
          <div className="space-y-6">
            {/* ── Toolbar ──────────────────────────────────────── */}
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <Wrench className="w-5 h-5 text-shogun-blue" /> {t('katana.tool_connectors')}
                <span className="text-[10px] font-normal bg-shogun-card border border-shogun-border px-1.5 py-0.5 rounded text-shogun-subdued">
                  {tools.length} active
                </span>
              </h3>
              <button
                id="register-tool-btn"
                onClick={() => setShowRegisterTool((v) => !v)}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-lg border text-[10px] font-bold uppercase tracking-widest transition-all",
                  showRegisterTool
                    ? "bg-shogun-blue/10 border-shogun-blue/40 text-shogun-blue"
                    : "border-shogun-border text-shogun-subdued hover:text-shogun-blue hover:border-shogun-blue/40 hover:bg-shogun-blue/5"
                )}
              >
                {showRegisterTool ? <X className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
                {showRegisterTool ? t('common.cancel') : t('katana.register_new_tool')}
              </button>
            </div>

            {/* ── Register Panel ────────────────────────────────── */}
            {showRegisterTool && (
              <div className="shogun-card border-shogun-blue/30 animate-in slide-in-from-top-3 duration-300">
                <div className="flex items-center justify-between mb-5">
                  <h4 className="font-bold text-shogun-text flex items-center gap-2">
                    <Puzzle className="w-4 h-4 text-shogun-blue" /> {t('katana.register_tool_connector')}
                  </h4>
                  {/* Mode toggle */}
                  <div className="flex items-center gap-1 p-1 bg-[#050508] border border-shogun-border rounded-lg">
                    {(['quick', 'manual'] as RegisterMode[]).map((m) => (
                      <button
                        key={m}
                        onClick={() => setRegisterMode(m)}
                        className={cn(
                          "px-3 py-1 rounded text-[10px] font-bold uppercase tracking-widest transition-all",
                          registerMode === m
                            ? "bg-shogun-blue text-white shadow"
                            : "text-shogun-subdued hover:text-shogun-text"
                        )}
                      >
                        {m === 'quick' ? t('katana.quick_pick') : t('katana.manual')}
                      </button>
                    ))}
                  </div>
                </div>

                <form onSubmit={handleRegisterTool}>
                  {/* ── QUICK PICK MODE ─────────────────────────── */}
                  {registerMode === 'quick' && (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                      {/* Search + list */}
                      <div className="space-y-3">
                        <div className="relative">
                          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-shogun-subdued" />
                          <input
                            type="text"
                            placeholder={t('katana.search_apis')}
                            value={apiSearch}
                            onChange={(e) => setApiSearch(e.target.value)}
                            className="w-full bg-[#050508] border border-shogun-border rounded-lg pl-9 pr-3 py-2.5 text-sm focus:border-shogun-blue outline-none"
                          />
                        </div>
                        <div className="h-64 overflow-y-auto space-y-1 pr-1 scrollbar-thin scrollbar-thumb-shogun-border scrollbar-track-transparent">
                          {filteredApis.length === 0 ? (
                            <p className="text-xs text-shogun-subdued italic text-center py-8">{t('katana.no_apis_match')}</p>
                          ) : filteredApis.map((api) => (
                            <button
                              key={api.name}
                              type="button"
                              onClick={() => { setSelectedApi(api); setQuickApiKey(''); }}
                              className={cn(
                                "w-full text-left px-3 py-2.5 rounded-lg border transition-all group flex items-center justify-between gap-2",
                                selectedApi?.name === api.name
                                  ? "border-shogun-blue/40 bg-shogun-blue/10 text-shogun-text"
                                  : "border-transparent hover:border-shogun-border hover:bg-shogun-card text-shogun-subdued hover:text-shogun-text"
                              )}
                            >
                              <div className="min-w-0">
                                <p className="text-xs font-bold truncate">{api.name}</p>
                                <p className="text-[10px] truncate opacity-70">{api.description}</p>
                              </div>
                              <ChevronRight className={cn(
                                "w-3.5 h-3.5 shrink-0 transition-all",
                                selectedApi?.name === api.name ? "text-shogun-blue opacity-100" : "opacity-0 group-hover:opacity-50"
                              )} />
                            </button>
                          ))}
                        </div>
                        <p className="text-[9px] text-shogun-subdued text-center">{filteredApis.length} APIs in catalog</p>
                      </div>

                      {/* Preview panel */}
                      <div className="flex flex-col">
                        {selectedApi ? (
                          <div className="flex-1 bg-[#050508] border border-shogun-border rounded-xl p-5 space-y-4">
                            <div>
                              <h5 className="font-bold text-shogun-text text-base">{selectedApi.name}</h5>
                              <p className="text-xs text-shogun-subdued mt-1 leading-relaxed">{selectedApi.description}</p>
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-[10px]">
                              {[
                                { label: t('katana.endpoint'), value: selectedApi.base_url },
                                { label: t('katana.auth'),     value: selectedApi.auth_type.replace('_', ' ').toUpperCase() },
                                { label: t('katana.type'),     value: selectedApi.connector_type.toUpperCase() },
                                { label: t('katana.risk'),     value: selectedApi.risk_level.toUpperCase() },
                              ].map(({ label, value }) => (
                                <div key={label} className="space-y-0.5">
                                  <p className="text-shogun-subdued uppercase tracking-widest font-bold">{label}</p>
                                  <p className="text-shogun-text font-mono truncate">{value}</p>
                                </div>
                              ))}
                            </div>
                            <div className="flex items-center gap-2 pt-1">
                              <Globe className="w-3 h-3 text-shogun-subdued shrink-0" />
                              <a
                                href={`https://www.google.com/search?q=${encodeURIComponent(selectedApi.name + ' API documentation')}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[10px] text-shogun-blue hover:underline truncate"
                              >
                                Find documentation →
                              </a>
                            </div>

                            {/* API Key field — shown only when auth is required */}
                            {selectedApi.auth_type !== 'none' && (
                              <div className="space-y-1.5 pt-1 border-t border-shogun-border/50">
                                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-1.5">
                                  <ShieldCheck className="w-3 h-3 text-shogun-gold" />
                                  API Key
                                  <span className="text-shogun-subdued/50 normal-case font-normal tracking-normal">({selectedApi.auth_type.replace('_', ' ')})</span>
                                </label>
                                <input
                                  type="password"
                                  placeholder="Paste your API key here…"
                                  value={quickApiKey}
                                  onChange={e => setQuickApiKey(e.target.value)}
                                  className="w-full bg-shogun-bg border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-gold focus:ring-1 focus:ring-shogun-gold/20 outline-none font-mono text-xs transition-all"
                                />
                                <p className="text-[9px] text-shogun-subdued/60">
                                  Stored locally in the connector config. Never sent to third parties.
                                </p>
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="flex-1 flex flex-col items-center justify-center text-center bg-[#050508] border border-dashed border-shogun-border rounded-xl p-8 gap-3">
                            <Puzzle className="w-8 h-8 text-shogun-subdued opacity-40" />
                            <p className="text-xs text-shogun-subdued">{t('katana.select_api_preview')}</p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* ── MANUAL ENTRY MODE ───────────────────────── */}
                  {registerMode === 'manual' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.tool_name', 'Tool Name *')}</label>
                        <input
                          required
                          type="text"
                          placeholder="e.g. Stripe Billing"
                          value={newTool.name}
                          onChange={(e) => setNewTool({ ...newTool, name: e.target.value, slug: toSlug(e.target.value) })}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.slug', 'Slug *')}</label>
                        <input
                          required
                          type="text"
                          placeholder="auto-generated"
                          value={newTool.slug}
                          onChange={(e) => setNewTool({ ...newTool, slug: e.target.value })}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none font-mono"
                        />
                      </div>
                      <div className="space-y-1.5 md:col-span-2">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.base_url', 'Base URL')}</label>
                        <input
                          type="text"
                          placeholder="https://api.example.com/v1"
                          value={newTool.base_url}
                          onChange={(e) => setNewTool({ ...newTool, base_url: e.target.value })}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none font-mono"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.connector_type', 'Connector Type')}</label>
                        <select
                          value={newTool.connector_type}
                          onChange={(e) => setNewTool({ ...newTool, connector_type: e.target.value as ConnectorTypeVal })}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                        >
                          {CONNECTOR_TYPES.map((t) => (
                            <option key={t} value={t}>{t.toUpperCase()}</option>
                          ))}
                        </select>
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.auth_type', 'Auth Type')}</label>
                        <select
                          value={newTool.auth_type}
                          onChange={(e) => setNewTool({ ...newTool, auth_type: e.target.value as AuthTypeVal })}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                        >
                          {AUTH_TYPES.map((t) => (
                            <option key={t} value={t}>{t.replace('_', ' ').toUpperCase()}</option>
                          ))}
                        </select>
                      </div>
                      <div className="space-y-2">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.risk_level', 'Risk Level')}</label>
                        <div className="flex gap-2">
                          {RISK_LEVELS.map((r) => (
                            <button
                              key={r}
                              type="button"
                              onClick={() => setNewTool({ ...newTool, risk_level: r })}
                              className={cn(
                                "flex-1 py-2 rounded-lg border text-[9px] font-bold uppercase tracking-widest transition-all",
                                newTool.risk_level === r
                                  ? riskColor(r) + ' border-opacity-100'
                                  : 'border-shogun-border text-shogun-subdued hover:border-shogun-blue/30'
                              )}
                            >
                              {r}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* ── Submit ─────────────────────────────────── */}
                  <div className="flex items-center gap-3 mt-6 pt-5 border-t border-shogun-border">
                    <button
                      type="submit"
                      disabled={registerSaving || (registerMode === 'quick' && !selectedApi)}
                      className="flex items-center gap-2 px-6 py-2.5 bg-shogun-blue hover:bg-shogun-blue/90 disabled:opacity-40 disabled:cursor-not-allowed text-white font-bold rounded-lg text-sm transition-all"
                    >
                      {registerSaving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                      {t('katana.register_connector')}
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowRegisterTool(false)}
                      className="px-4 py-2.5 text-sm font-bold text-shogun-subdued hover:text-shogun-text transition-colors"
                    >
                      Cancel
                    </button>
                    {registerMode === 'quick' && !selectedApi && (
                      <p className="text-[10px] text-shogun-subdued ml-auto">{t('katana.select_api_first')}</p>
                    )}
                  </div>
                </form>
              </div>
            )}

            {/* ── Tool cards grid ───────────────────────────────── */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {loading ? (
                <div className="col-span-3 p-12 text-center shogun-card opacity-50">
                  <RefreshCw className="w-8 h-8 animate-spin mx-auto text-shogun-blue mb-4" />
                  <p className="text-xs uppercase tracking-widest font-bold">{t('katana.loading_connectors')}</p>
                </div>
              ) : tools.length === 0 ? (
                <div className="col-span-3 p-12 text-center shogun-card border-dashed">
                  <Wrench className="w-8 h-8 text-shogun-subdued opacity-30 mx-auto mb-3" />
                  <p className="text-shogun-subdued italic text-sm">{t('katana.no_tools')}</p>
                  <button
                    onClick={() => setShowRegisterTool(true)}
                    className="mt-4 text-[10px] font-bold text-shogun-blue hover:text-shogun-gold uppercase tracking-widest transition-colors"
                  >
                    + Register your first tool
                  </button>
                </div>
              ) : tools.map((tool) => (
                <div key={tool.id} className="shogun-card hover:border-shogun-blue/30 transition-all group relative">
                  {/* Delete button */}
                  {tool.source !== 'builtin' && !tool.config?.builtin && (
                    <button
                      onClick={() => handleDeleteTool(tool.id, tool.name)}
                      className="absolute top-3 right-3 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-red-500/10 text-red-500/50 hover:text-red-500 transition-all"
                      title={t('katana.remove_connector')}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}

                  <div className="flex items-start gap-3 mb-4">
                    <div className="w-10 h-10 rounded-lg bg-[#050508] border border-shogun-border flex items-center justify-center text-shogun-subdued group-hover:text-shogun-blue transition-colors shrink-0">
                      <Wrench className="w-5 h-5" />
                    </div>
                    <div className="min-w-0">
                      <h4 className="font-bold text-shogun-text truncate flex items-center gap-2">
                        {tool.name}
                        {(tool.source === 'builtin' || tool.config?.builtin) && (
                          <span className="text-[8px] uppercase tracking-widest text-indigo-300 border border-indigo-400/30 bg-indigo-500/10 rounded px-1.5 py-0.5">
                            Standard
                          </span>
                        )}
                      </h4>
                      <p className="text-[10px] text-shogun-subdued font-mono truncate">{tool.slug}</p>
                    </div>
                  </div>

                  {tool.base_url && (
                    <p className="text-[10px] text-shogun-subdued font-mono truncate mb-3 bg-[#050508] px-2 py-1 rounded border border-shogun-border">
                      {tool.base_url}
                    </p>
                  )}

                  <div className="flex items-center justify-between pt-3 border-t border-shogun-border">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[8px] uppercase tracking-widest font-bold px-1.5 py-0.5 rounded bg-[#050508] border border-shogun-border text-shogun-subdued">
                        {tool.connector_type || 'api'}
                      </span>
                      <span className={cn(
                        "text-[8px] uppercase tracking-widest font-bold px-1.5 py-0.5 rounded border",
                        riskColor(tool.risk_level as RiskLevelVal || 'low')
                      )}>
                        {tool.risk_level || 'low'}
                      </span>
                    </div>
                    <span className={cn(
                      "text-[8px] uppercase tracking-widest font-bold px-1.5 py-0.5 rounded border",
                      tool.status === 'connected' || tool.status === 'active'
                        ? 'text-green-400 border-green-400/30 bg-green-400/5'
                        : tool.status === 'disabled'
                        ? 'text-shogun-subdued border-shogun-border bg-shogun-card'
                        : 'text-yellow-400 border-yellow-400/30 bg-yellow-400/5'
                    )}>
                      {tool.status || 'not_configured'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════════════════════
            MCP SERVERS TAB
        ════════════════════════════════════════════════════════ */}
        {activeTab === 'tools' && (
          <div className="space-y-6 pt-12 mt-12 border-t border-shogun-border/30">
            {/* ── Toolbar ──────────────────────────────────────── */}
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <Layers className="w-5 h-5 text-indigo-500" /> {t('katana.mcp_servers', 'MCP Servers')}
                <span className="text-[10px] font-normal bg-shogun-card border border-shogun-border px-1.5 py-0.5 rounded text-shogun-subdued">
                  {tools.filter(t => t.connector_type === 'mcp').length} active
                </span>
              </h3>
              <button
                onClick={() => setShowRegisterMcp((v) => !v)}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-lg border text-[10px] font-bold uppercase tracking-widest transition-all",
                  showRegisterMcp
                    ? "bg-indigo-500/10 border-indigo-500/40 text-indigo-400"
                    : "border-shogun-border text-shogun-subdued hover:text-indigo-400 hover:border-indigo-500/40 hover:bg-indigo-500/5"
                )}
              >
                {showRegisterMcp ? <X className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
                {showRegisterMcp ? t('common.cancel') : t('katana.register_mcp', 'Register MCP')}
              </button>
            </div>

            {/* ── Register Panel ────────────────────────────────── */}
            {showRegisterMcp && (
              <div className="shogun-card border-indigo-500/30 animate-in slide-in-from-top-3 duration-300">
                <div className="flex items-center justify-between mb-5">
                  <h4 className="font-bold text-shogun-text flex items-center gap-2">
                    <Puzzle className="w-4 h-4 text-indigo-500" /> {t('katana.register_mcp_server', 'Register MCP Server')}
                  </h4>
                  {/* Mode toggle */}
                  <div className="flex items-center gap-1 p-1 bg-[#050508] border border-shogun-border rounded-lg">
                    {(['quick', 'manual'] as const).map((m) => (
                      <button
                        key={m}
                        onClick={() => setMcpRegisterMode(m)}
                        className={cn(
                          "px-3 py-1 rounded text-[10px] font-bold uppercase tracking-widest transition-all",
                          mcpRegisterMode === m
                            ? "bg-indigo-500 text-white shadow"
                            : "text-shogun-subdued hover:text-shogun-text"
                        )}
                      >
                        {m === 'quick' ? t('katana.quick_pick') : t('katana.manual')}
                      </button>
                    ))}
                  </div>
                </div>

                <form onSubmit={handleRegisterMcp}>
                  {/* ── QUICK PICK MODE ─────────────────────────── */}
                  {mcpRegisterMode === 'quick' && (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                      {/* Search + list */}
                      <div className="space-y-3">
                        <div className="relative">
                          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-shogun-subdued" />
                          <input
                            type="text"
                            placeholder="Search MCP servers..."
                            value={mcpSearch}
                            onChange={(e) => setMcpSearch(e.target.value)}
                            className="w-full bg-[#050508] border border-shogun-border rounded-lg pl-9 pr-3 py-2.5 text-sm focus:border-indigo-500 outline-none"
                          />
                        </div>
                        <div className="h-64 overflow-y-auto space-y-1 pr-1 scrollbar-thin scrollbar-thumb-shogun-border scrollbar-track-transparent">
                          {filteredMcps.length === 0 ? (
                            <p className="text-xs text-shogun-subdued italic text-center py-8">No MCP servers match your search.</p>
                          ) : filteredMcps.map((mcp) => (
                            <button
                              key={mcp.name}
                              type="button"
                              onClick={() => { setSelectedMcp(mcp); setMcpEnvValues({}); }}
                              className={cn(
                                "w-full text-left px-3 py-2.5 rounded-lg border transition-all group flex items-center justify-between gap-2",
                                selectedMcp?.name === mcp.name
                                  ? "border-indigo-500/40 bg-indigo-500/10 text-shogun-text"
                                  : "border-transparent hover:border-shogun-border hover:bg-shogun-card text-shogun-subdued hover:text-shogun-text"
                              )}
                            >
                              <div className="min-w-0">
                                <p className="text-xs font-bold truncate">{mcp.name}</p>
                                <p className="text-[10px] truncate opacity-70">{mcp.category}</p>
                              </div>
                              <ChevronRight className={cn(
                                "w-3.5 h-3.5 shrink-0 transition-all",
                                selectedMcp?.name === mcp.name ? "text-indigo-400 opacity-100" : "opacity-0 group-hover:opacity-50"
                              )} />
                            </button>
                          ))}
                        </div>
                      </div>

                      {/* Preview panel */}
                      <div className="flex flex-col">
                        {selectedMcp ? (
                          <div className="flex-1 bg-[#050508] border border-shogun-border rounded-xl p-5 space-y-4">
                            <div>
                              <h5 className="font-bold text-shogun-text text-base">{selectedMcp.name}</h5>
                              <p className="text-xs text-shogun-subdued mt-1 leading-relaxed">{selectedMcp.description}</p>
                            </div>
                            <div className="grid grid-cols-2 gap-2 text-[10px]">
                              {[
                                { label: 'COMMAND',   value: selectedMcp.transport === 'stdio' ? `${selectedMcp.command} ${selectedMcp.args.join(' ')}` : selectedMcp.github_url },
                                { label: 'TRANSPORT', value: selectedMcp.transport.toUpperCase() },
                                { label: 'RISK',      value: selectedMcp.risk_level.toUpperCase() },
                              ].map(({ label, value }) => (
                                <div key={label} className={cn("space-y-0.5", label === 'COMMAND' && "col-span-2")}>
                                  <p className="text-shogun-subdued uppercase tracking-widest font-bold">{label}</p>
                                  <p className="text-shogun-text font-mono truncate">{value}</p>
                                </div>
                              ))}
                            </div>
                            <div className="flex items-center gap-2 pt-1">
                              <Globe className="w-3 h-3 text-shogun-subdued shrink-0" />
                              <a
                                href={selectedMcp.github_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-[10px] text-indigo-400 hover:underline truncate"
                              >
                                View Repository →
                              </a>
                            </div>

                            {selectedMcp.env_keys.length > 0 && (
                              <div className="space-y-3 pt-3 border-t border-shogun-border/50">
                                <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-1.5">
                                  <ShieldCheck className="w-3 h-3 text-shogun-gold" />
                                  Required Environment Variables
                                </label>
                                {selectedMcp.env_keys.map(key => (
                                  <input
                                    key={key}
                                    type="password"
                                    placeholder={key}
                                    value={mcpEnvValues[key] || ''}
                                    onChange={e => setMcpEnvValues({ ...mcpEnvValues, [key]: e.target.value })}
                                    className="w-full bg-shogun-bg border border-shogun-border rounded-lg p-2.5 text-sm focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/20 outline-none font-mono text-xs transition-all"
                                  />
                                ))}
                              </div>
                            )}
                          </div>
                        ) : (
                          <div className="flex-1 flex flex-col items-center justify-center text-center bg-[#050508] border border-dashed border-shogun-border rounded-xl p-8 gap-3">
                            <Puzzle className="w-8 h-8 text-shogun-subdued opacity-40" />
                            <p className="text-xs text-shogun-subdued">Select an MCP server from the catalog to configure it.</p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* ── MANUAL ENTRY MODE ───────────────────────── */}
                  {mcpRegisterMode === 'manual' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Server Name *</label>
                        <input
                          required
                          type="text"
                          placeholder="e.g. My Custom MCP"
                          value={newMcp.name}
                          onChange={(e) => setNewMcp({ ...newMcp, name: e.target.value })}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-indigo-500 outline-none"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Transport</label>
                        <select
                          value={newMcp.transport}
                          onChange={(e) => setNewMcp({ ...newMcp, transport: e.target.value as 'stdio' | 'sse' })}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-indigo-500 outline-none"
                        >
                          <option value="stdio">STDIO (Local command)</option>
                          <option value="sse">SSE (Remote URL)</option>
                        </select>
                      </div>
                      
                      {newMcp.transport === 'stdio' ? (
                        <>
                          <div className="space-y-1.5">
                            <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Command *</label>
                            <input
                              required
                              type="text"
                              placeholder="e.g. npx"
                              value={newMcp.command}
                              onChange={(e) => setNewMcp({ ...newMcp, command: e.target.value })}
                              className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-indigo-500 outline-none font-mono"
                            />
                          </div>
                          <div className="space-y-1.5">
                            <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Arguments</label>
                            <input
                              type="text"
                              placeholder="e.g. -y @modelcontextprotocol/server-postgres"
                              value={newMcp.args}
                              onChange={(e) => setNewMcp({ ...newMcp, args: e.target.value })}
                              className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-indigo-500 outline-none font-mono"
                            />
                          </div>
                        </>
                      ) : (
                        <div className="space-y-1.5 md:col-span-2">
                          <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">SSE URL *</label>
                          <input
                            required
                            type="text"
                            placeholder="https://mcp.example.com/sse"
                            value={newMcp.command}
                            onChange={(e) => setNewMcp({ ...newMcp, command: e.target.value })}
                            className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-indigo-500 outline-none font-mono"
                          />
                        </div>
                      )}

                      <div className="space-y-2">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Risk Level</label>
                        <div className="flex gap-2">
                          {RISK_LEVELS.map((r) => (
                            <button
                              key={r}
                              type="button"
                              onClick={() => setNewMcp({ ...newMcp, risk_level: r })}
                              className={cn(
                                "flex-1 py-2 rounded-lg border text-[9px] font-bold uppercase tracking-widest transition-all",
                                newMcp.risk_level === r
                                  ? riskColor(r) + ' border-opacity-100'
                                  : 'border-shogun-border text-shogun-subdued hover:border-indigo-500/30'
                              )}
                            >
                              {r}
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* ── Submit ─────────────────────────────────── */}
                  <div className="flex items-center gap-3 mt-6 pt-5 border-t border-shogun-border">
                    <button
                      type="submit"
                      disabled={registerSaving || (mcpRegisterMode === 'quick' && (!selectedMcp || selectedMcp.env_keys.some(k => !mcpEnvValues[k])))}
                      className="flex items-center gap-2 px-6 py-2.5 bg-indigo-500 hover:bg-indigo-600 disabled:opacity-40 disabled:cursor-not-allowed text-white font-bold rounded-lg text-sm transition-all"
                    >
                      {registerSaving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                      Register MCP Server
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowRegisterMcp(false)}
                      className="px-4 py-2.5 text-sm font-bold text-shogun-subdued hover:text-shogun-text transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            )}
            {/* ── MCP cards grid ───────────────────────────────── */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {loading ? (
                <div className="col-span-3 p-12 text-center shogun-card opacity-50">
                  <RefreshCw className="w-8 h-8 animate-spin mx-auto text-indigo-500 mb-4" />
                  <p className="text-xs uppercase tracking-widest font-bold">Loading MCPs</p>
                </div>
              ) : tools.filter(t => t.connector_type === 'mcp').length === 0 ? (
                <div className="col-span-3 p-12 text-center shogun-card border-dashed">
                  <Layers className="w-8 h-8 text-shogun-subdued opacity-30 mx-auto mb-3" />
                  <p className="text-shogun-subdued italic text-sm">No MCP servers registered</p>
                  <button
                    onClick={() => setShowRegisterMcp(true)}
                    className="mt-4 text-[10px] font-bold text-indigo-400 hover:text-indigo-300 uppercase tracking-widest transition-colors"
                  >
                    + Register your first MCP
                  </button>
                </div>
              ) : tools.filter(t => t.connector_type === 'mcp').map((tool) => (
                <div key={tool.id} className="shogun-card hover:border-indigo-500/30 transition-all group relative">
                  {tool.source !== 'builtin' && !tool.config?.builtin && (
                    <button
                      onClick={() => handleDeleteTool(tool.id, tool.name)}
                      className="absolute top-3 right-3 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-red-500/10 text-red-500/50 hover:text-red-500 transition-all"
                      title={t('katana.remove_connector')}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}

                  <div className="flex items-start gap-3 mb-4">
                    <div className="w-10 h-10 rounded-lg bg-[#050508] border border-shogun-border flex items-center justify-center text-shogun-subdued group-hover:text-indigo-400 transition-colors shrink-0">
                      <Layers className="w-5 h-5" />
                    </div>
                    <div className="min-w-0">
                      <h4 className="font-bold text-shogun-text truncate flex items-center gap-2">
                        {tool.name}
                        {(tool.source === 'builtin' || tool.config?.builtin) && (
                          <span className="text-[8px] uppercase tracking-widest text-indigo-300 border border-indigo-400/30 bg-indigo-500/10 rounded px-1.5 py-0.5">
                            Standard
                          </span>
                        )}
                      </h4>
                      <p className="text-[10px] text-shogun-subdued font-mono truncate">{tool.config?.transport === 'sse' ? 'SSE' : 'STDIO'} • {tool.slug}</p>
                    </div>
                  </div>

                  {tool.config?.command && (
                    <p className="text-[10px] text-shogun-subdued font-mono truncate mb-3 bg-[#050508] px-2 py-1 rounded border border-shogun-border" title={tool.config.transport === 'stdio' ? `${tool.config.command} ${(tool.config.args || []).join(' ')}` : tool.base_url}>
                      {tool.config.transport === 'stdio' ? `${tool.config.command} ${(tool.config.args || []).join(' ')}` : tool.base_url}
                    </p>
                  )}

                  <div className="flex items-center justify-between pt-3 border-t border-shogun-border">
                    <div className="flex items-center gap-1.5">
                      <span className="text-[8px] uppercase tracking-widest font-bold px-1.5 py-0.5 rounded bg-[#050508] border border-shogun-border text-shogun-subdued">
                        MCP
                      </span>
                      <span className={cn(
                        "text-[8px] uppercase tracking-widest font-bold px-1.5 py-0.5 rounded border",
                        riskColor(tool.risk_level as RiskLevelVal || 'low')
                      )}>
                        {tool.risk_level || 'low'}
                      </span>
                    </div>
                    <span className={cn(
                      "text-[8px] uppercase tracking-widest font-bold px-1.5 py-0.5 rounded border",
                      tool.status === 'connected' || tool.status === 'active'
                        ? 'text-green-400 border-green-400/30 bg-green-400/5'
                        : tool.status === 'disabled'
                        ? 'text-shogun-subdued border-shogun-border bg-shogun-card'
                        : 'text-yellow-400 border-yellow-400/30 bg-yellow-400/5'
                    )}>
                      {tool.status || 'not_configured'}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}


        {/* ════════════════════════════════════════════════════════
            ROUTING TAB
        ════════════════════════════════════════════════════════ */}
        {activeTab === 'routing' && (
          <div className="space-y-6">
            <ModelRoutingPanel
              isEditingProfiles={showRoutingProfileEditor}
              onEditProfiles={() => setShowRoutingProfileEditor(value => !value)}
            />

            {showRoutingProfileEditor && <div className="space-y-6 animate-in slide-in-from-top-2 duration-200">
            {/* ── Header ──────────────────────────────────────── */}
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <SlidersHorizontal className="w-5 h-5 text-shogun-blue" /> {t('katana.routing_profiles')}
                <span className="text-[10px] font-normal bg-shogun-card border border-shogun-border px-1.5 py-0.5 rounded text-shogun-subdued">
                  {routingProfiles.length} profiles
                </span>
              </h3>
              <button
                onClick={() => setShowCreateProfile(v => !v)}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 rounded-lg border text-[10px] font-bold uppercase tracking-widest transition-all",
                  showCreateProfile
                    ? "bg-shogun-blue/10 border-shogun-blue/40 text-shogun-blue"
                    : "border-shogun-border text-shogun-subdued hover:text-shogun-blue hover:border-shogun-blue/40 hover:bg-shogun-blue/5"
                )}
              >
                {showCreateProfile ? <X className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
                {showCreateProfile ? t('common.cancel') : t('katana.new_profile')}
              </button>
            </div>

            {/* ── {t('katana.create_profile')} Panel ──────────────────────── */}
            {showCreateProfile && (
              <div className="shogun-card border-shogun-blue/30 animate-in slide-in-from-top-3 duration-300">
                <h4 className="font-bold text-shogun-text flex items-center gap-2 mb-4">
                  <GitBranch className="w-4 h-4 text-shogun-blue" /> {t('katana.new_routing_profile')}
                </h4>
                <form onSubmit={handleCreateProfile}>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.profile_name', 'Profile Name *')}</label>
                      <input
                        required
                        type="text"
                        placeholder="e.g. Quality First"
                        value={newProfile.name}
                        onChange={e => setNewProfile({ ...newProfile, name: e.target.value })}
                        className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.description', 'Description')}</label>
                      <input
                        type="text"
                        placeholder="Optional short description"
                        value={newProfile.description}
                        onChange={e => setNewProfile({ ...newProfile, description: e.target.value })}
                        className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                      />
                    </div>
                  </div>
                  <div className="flex items-center gap-4 mt-4 pt-4 border-t border-shogun-border">
                    <label className="flex items-center gap-2 cursor-pointer text-sm text-shogun-subdued hover:text-shogun-text transition-colors">
                      <input
                        type="checkbox"
                        checked={newProfile.is_default}
                        onChange={e => setNewProfile({ ...newProfile, is_default: e.target.checked })}
                        className="accent-shogun-blue"
                      />
                      {t('katana.set_as_default_profile')}
                    </label>
                    <button
                      type="submit"
                      disabled={profileSaving || !newProfile.name.trim()}
                      className="flex items-center gap-2 px-5 py-2 bg-shogun-blue hover:bg-shogun-blue/90 disabled:opacity-40 text-white font-bold rounded-lg text-sm transition-all"
                    >
                      {profileSaving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                      Create Profile
                    </button>
                  </div>
                </form>
              </div>
            )}

            {/* ── Profiles list ────────────────────────────── */}
            {loading ? (
              <div className="p-12 text-center shogun-card opacity-50">
                <RefreshCw className="w-8 h-8 animate-spin mx-auto text-shogun-blue mb-4" />
                <p className="text-xs uppercase tracking-widest font-bold">{t('katana.loading_profiles')}</p>
              </div>
            ) : routingProfiles.length === 0 ? (
              <div className="shogun-card text-center py-20 space-y-4 border-dashed">
                <div className="w-16 h-16 bg-shogun-blue/10 rounded-full flex items-center justify-center mx-auto">
                  <ArrowRightLeft className="w-8 h-8 text-shogun-blue" />
                </div>
                <div>
                  <h4 className="font-bold text-shogun-text">{t('katana.no_routing_profiles')}</h4>
                  <p className="text-sm text-shogun-subdued mt-1 max-w-sm mx-auto">
                    {t('katana.no_routing_profiles_desc')}
                  </p>
                </div>
                <button
                  onClick={() => setShowCreateProfile(true)}
                  className="text-[10px] font-bold text-shogun-blue hover:text-shogun-gold uppercase tracking-widest transition-colors"
                >
                  {t('katana.create_first_profile')}
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                {routingProfiles.map((profile) => {
                  const isExpanded = expandedProfileId === profile.id;
                  const rules: any[] = profile.rules || [];
                  return (
                    <div
                      key={profile.id}
                      className={cn(
                        "shogun-card transition-all",
                        profile.is_default ? "border-shogun-gold/40" : "hover:border-shogun-blue/30"
                      )}
                    >
                      {/* Profile header row */}
                      <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                          <div className={cn(
                            "w-12 h-12 rounded-xl flex items-center justify-center shrink-0",
                            profile.is_default ? "bg-shogun-gold/10 text-shogun-gold" : "bg-shogun-blue/10 text-shogun-blue"
                          )}>
                            {profile.is_default ? <Star className="w-5 h-5" /> : <SlidersHorizontal className="w-5 h-5" />}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <h4 className="font-bold text-shogun-text">{profile.name}</h4>
                              {profile.is_default && (
                                <span className="text-[8px] bg-shogun-gold/10 text-shogun-gold px-1.5 py-0.5 rounded border border-shogun-gold/30 font-bold uppercase tracking-widest">
                                  {t('katana.default')}
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-shogun-subdued mt-0.5">
                              {profile.description || t('katana.no_description')}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-1 shrink-0">
                          {/* Rule count toggle */}
                          <button
                            onClick={() => {
                              setExpandedProfileId(isExpanded ? null : profile.id);
                              setShowAddRule(false);
                            }}
                            className={cn(
                              "flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-[10px] font-bold uppercase tracking-widest transition-all",
                              isExpanded
                                ? "border-shogun-blue/40 bg-shogun-blue/10 text-shogun-blue"
                                : "border-shogun-border text-shogun-subdued hover:border-shogun-blue/30 hover:text-shogun-text"
                            )}
                          >
                            <Layers className="w-3 h-3" />
                            {rules.length} {rules.length === 1 ? t('katana.rule') : t('katana.rules')}
                            {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          </button>

                          {/* Set default */}
                          {!profile.is_default && (
                            <button
                              onClick={() => handleSetDefault(profile.id)}
                              className="p-2 hover:bg-shogun-gold/10 text-shogun-subdued hover:text-shogun-gold rounded-lg transition-colors"
                              title={t('katana.set_as_default')}
                            >
                              <StarOff className="w-4 h-4" />
                            </button>
                          )}

                          {/* Delete profile */}
                          <button
                            onClick={() => handleDeleteProfile(profile.id, profile.name)}
                            className="p-2 hover:bg-red-500/10 text-red-500/40 hover:text-red-500 rounded-lg transition-colors"
                            title={t('katana.delete_profile')}
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>

                      {/* ── Expanded rules section ─────────────── */}
                      {isExpanded && (
                        <div className="mt-5 pt-5 border-t border-shogun-border space-y-3 animate-in slide-in-from-top-2 duration-200">

                          {/* Header */}
                          <div className="flex items-center justify-between">
                            <p className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.routing_rules')}</p>
                            {!showAddRule && (
                              <button
                                onClick={() => setShowAddRule(true)}
                                className="flex items-center gap-1 text-[10px] font-bold text-shogun-blue hover:text-shogun-gold uppercase tracking-widest transition-colors"
                              >
                                <Plus className="w-3 h-3" /> {t('katana.add_rule')}
                              </button>
                            )}
                          </div>

                          {/* Existing rules */}
                          {rules.length === 0 && !showAddRule ? (
                            <div className="text-center py-6 bg-[#050508] rounded-xl border border-dashed border-shogun-border">
                              <p className="text-xs text-shogun-subdued italic">{t('katana.no_rules')}</p>
                            </div>
                          ) : (
                            <div className="space-y-2">
                              {rules.map((rule: any, idx: number) => {
                                const primaryProvider = providers.find(p => p.id === rule.primary_model_id);
                                return (
                                  <div key={idx} className="flex items-center gap-3 bg-[#050508] border border-shogun-border rounded-xl p-3 group">
                                    {/* Task type */}
                                    <div className="w-8 h-8 rounded-lg bg-shogun-blue/10 flex items-center justify-center shrink-0">
                                      <GitBranch className="w-4 h-4 text-shogun-blue" />
                                    </div>
                                    <div className="flex-1 grid grid-cols-2 md:grid-cols-4 gap-x-4 gap-y-1">
                                      <div>
                                        <p className="text-[9px] text-shogun-subdued uppercase tracking-widest font-bold">{t('katana.task_type_label')}</p>
                                        <p className="text-xs font-bold text-shogun-text">
                                          {rule.task_type === '*' ? t('katana.all_tasks') : rule.task_type}
                                        </p>
                                      </div>
                                      <div>
                                        <p className="text-[9px] text-shogun-subdued uppercase tracking-widest font-bold">{t('katana.primary_model')}</p>
                                        <p className="text-xs font-bold text-shogun-text truncate">
                                          {primaryProvider?.name || (
                                            <span className="text-red-400/70 text-[10px]">{t('katana.unlinked')}</span>
                                          )}
                                        </p>
                                        <p className="text-[9px] text-shogun-subdued mt-0.5">
                                          {rule.fallback_model_ids?.length || 0} fallback(s)
                                        </p>
                                      </div>
                                      <div>
                                        <p className="text-[9px] text-shogun-subdued uppercase tracking-widest font-bold">{t('katana.latency')}</p>
                                        <p className="text-xs text-shogun-text">{rule.latency_bias || <span className="text-shogun-subdued">—</span>}</p>
                                      </div>
                                      <div>
                                        <p className="text-[9px] text-shogun-subdued uppercase tracking-widest font-bold">{t('katana.cost')}</p>
                                        <p className="text-xs text-shogun-text">{rule.cost_bias || <span className="text-shogun-subdued">—</span>}</p>
                                      </div>
                                    </div>
                                    {/* Actions */}
                                    <div className="flex items-center gap-2 flex-none pl-4 border-l border-shogun-border/30">
                                      <button
                                        onClick={(e) => { e.stopPropagation(); handleStartEditRule(idx, rule); }}
                                        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-shogun-blue/10 border border-shogun-blue/20 hover:bg-shogun-blue/20 text-shogun-blue transition-all"
                                        title={t('common.edit')}
                                      >
                                        <Edit2 className="w-3.5 h-3.5" />
                                        <span className="text-[10px] font-bold uppercase tracking-wider">{t('common.edit')}</span>
                                      </button>
                                      <button
                                        onClick={(e) => { e.stopPropagation(); handleDeleteRule(profile.id, rules, idx); }}
                                        className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-red-500/5 border border-red-500/10 hover:bg-red-500/10 text-red-500 transition-all"
                                        title={t('common.delete')}
                                      >
                                        <Trash2 className="w-3.5 h-3.5" />
                                        <span className="text-[10px] font-bold uppercase tracking-wider">{t('common.delete')}</span>
                                      </button>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}

                          {/* Add Rule form */}
                          {showAddRule && (
                            <div className="bg-shogun-blue/5 border border-shogun-blue/20 rounded-xl p-4 space-y-4 animate-in slide-in-from-top-2 duration-200">
                              <p className="text-[10px] font-bold text-shogun-blue uppercase tracking-widest flex items-center gap-1.5">
                                {editingRuleIdx !== null ? (
                                  <><Edit2 className="w-3 h-3" /> {t('katana.edit_routing_rule')}</>
                                ) : (
                                  <><Plus className="w-3 h-3" /> {t('katana.new_routing_rule')}</>
                                )}
                              </p>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {/* Task Type */}
                                <div className="space-y-1.5">
                                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.task_type', 'Task Type')}</label>
                                  <select
                                    value={newRule.task_type}
                                    onChange={e => setNewRule({ ...newRule, task_type: e.target.value })}
                                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue outline-none"
                                  >
                                    <option value="*">{t('katana.all_tasks_wildcard')}</option>
                                    <option value="research">{t('katana.task_research')}</option>
                                    <option value="code">{t('katana.task_code')}</option>
                                    <option value="analysis">{t('katana.task_analysis')}</option>
                                    <option value="creative">{t('katana.task_creative')}</option>
                                    <option value="summarize">{t('katana.task_summarize')}</option>
                                    <option value="planning">{t('katana.task_planning')}</option>
                                    <option value="qa">{t('katana.task_qa')}</option>
                                    <option value="chat">{t('katana.task_chat')}</option>
                                    <option value="extraction">{t('katana.task_extraction')}</option>
                                    <option value="translation">{t('katana.task_translation')}</option>
                                    <option value="vision">{t('katana.task_vision')}</option>
                                  </select>
                                </div>

                                {/* Primary Model */}
                                <div className="space-y-1.5">
                                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.primary_model_provider', 'Primary Model Provider *')}</label>
                                  <select
                                    value={newRule.primary_model_id}
                                    onChange={e => setNewRule({
                                      ...newRule,
                                      primary_model_id: e.target.value,
                                      fallback_model_ids: newRule.fallback_model_ids.filter(id => id !== e.target.value),
                                    })}
                                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue outline-none"
                                  >
                                    <option value="">{t('katana.select_provider')}</option>
                                    {providers.map(p => (
                                      <option key={p.id} value={p.id}>
                                        {p.name} — {p.provider_type}
                                      </option>
                                    ))}
                                    {providers.length === 0 && (
                                      <option disabled>{t('katana.no_providers_yet')}</option>
                                    )}
                                  </select>
                                  {providers.length === 0 && (
                                    <p className="text-[9px] text-yellow-400">⚠ {t('katana.add_provider_first')}</p>
                                  )}
                                </div>

                                {/* Latency Bias */}
                                <div className="space-y-1.5 md:col-span-2">
                                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Fallback Chain (in order)</label>
                                  <select
                                    value=""
                                    onChange={e => {
                                      const id = e.target.value;
                                      if (id && !newRule.fallback_model_ids.includes(id)) {
                                        setNewRule({ ...newRule, fallback_model_ids: [...newRule.fallback_model_ids, id] });
                                      }
                                    }}
                                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue outline-none"
                                  >
                                    <option value="">— Add fallback provider —</option>
                                    {providers
                                      .filter(p => p.id !== newRule.primary_model_id && !newRule.fallback_model_ids.includes(p.id))
                                      .map(p => <option key={p.id} value={p.id}>{p.name} — {p.provider_type}</option>)}
                                  </select>
                                  {newRule.fallback_model_ids.map((id, index) => {
                                    const fallback = providers.find(p => p.id === id);
                                    return (
                                      <div key={id} className="flex items-center gap-2 rounded-lg border border-shogun-border bg-[#050508] px-3 py-2">
                                        <span className="text-[10px] font-bold text-shogun-gold">#{index + 1}</span>
                                        <span className="flex-1 text-xs">{fallback?.name || 'Unlinked provider'}</span>
                                        <button type="button" disabled={index === 0} onClick={() => {
                                          const ids = [...newRule.fallback_model_ids];
                                          [ids[index - 1], ids[index]] = [ids[index], ids[index - 1]];
                                          setNewRule({ ...newRule, fallback_model_ids: ids });
                                        }} className="disabled:opacity-20"><ChevronUp className="w-3.5 h-3.5" /></button>
                                        <button type="button" disabled={index === newRule.fallback_model_ids.length - 1} onClick={() => {
                                          const ids = [...newRule.fallback_model_ids];
                                          [ids[index], ids[index + 1]] = [ids[index + 1], ids[index]];
                                          setNewRule({ ...newRule, fallback_model_ids: ids });
                                        }} className="disabled:opacity-20"><ChevronDown className="w-3.5 h-3.5" /></button>
                                        <button type="button" onClick={() => setNewRule({
                                          ...newRule,
                                          fallback_model_ids: newRule.fallback_model_ids.filter(item => item !== id),
                                        })}><X className="w-3.5 h-3.5 text-red-400" /></button>
                                      </div>
                                    );
                                  })}
                                  <p className="text-[9px] text-shogun-subdued">A model is tried after the previous model exhausts its configured retries or times out.</p>
                                </div>

                                {/* Latency Bias */}
                                <div className="space-y-1.5">
                                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.latency_bias', 'Latency Bias')}</label>
                                  <select
                                    value={newRule.latency_bias}
                                    onChange={e => setNewRule({ ...newRule, latency_bias: e.target.value })}
                                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue outline-none"
                                  >
                                    <option value="">{t('katana.none_unbiased')}</option>
                                    <option value="low">{t('katana.latency_low')}</option>
                                    <option value="medium">{t('katana.latency_medium')}</option>
                                    <option value="high">{t('katana.latency_high')}</option>
                                  </select>
                                </div>

                                {/* Cost Bias */}
                                <div className="space-y-1.5">
                                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.cost_bias', 'Cost Bias')}</label>
                                  <select
                                    value={newRule.cost_bias}
                                    onChange={e => setNewRule({ ...newRule, cost_bias: e.target.value })}
                                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue outline-none"
                                  >
                                    <option value="">{t('katana.none_unbiased')}</option>
                                    <option value="budget">{t('katana.cost_budget')}</option>
                                    <option value="standard">{t('katana.cost_standard')}</option>
                                    <option value="premium">{t('katana.cost_premium')}</option>
                                  </select>
                                </div>
                              </div>

                              <div className="flex items-center gap-3 pt-2">
                                  <button
                                    type="button"
                                    onClick={() => handleAddRule(profile.id, rules)}
                                    disabled={!newRule.primary_model_id}
                                    className="flex items-center gap-2 px-5 py-2 bg-shogun-blue hover:bg-shogun-blue/90 disabled:opacity-40 disabled:cursor-not-allowed text-white font-bold rounded-lg text-sm transition-all"
                                  >
                                    <Save className="w-3.5 h-3.5" /> {editingRuleIdx !== null ? t('katana.update_rule') : t('katana.save_rule')}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => { setShowAddRule(false); setEditingRuleIdx(null); setNewRule({ task_type: '*', primary_model_id: '', fallback_model_ids: [], latency_bias: '', cost_bias: '' }); }}
                                    className="px-4 py-2 text-sm text-shogun-subdued hover:text-shogun-text transition-colors font-bold"
                                  >
                                    {t('common.cancel')}
                                  </button>
                                {!newRule.primary_model_id && (
                                  <span className="text-[10px] text-shogun-subdued ml-auto">{t('katana.select_provider_continue')}</span>
                                )}
                              </div>
                            </div>
                          )}

                          {/* Routing logic legend */}
                          <div className="flex items-start gap-2 mt-2 px-1">
                            <Shield className="w-3 h-3 text-shogun-subdued mt-0.5 shrink-0" />
                            <p className="text-[10px] text-shogun-subdued leading-relaxed">
                              {t('katana.routing_legend')} <code className="text-shogun-blue font-mono">task_type</code> {t('katana.routing_legend_wins')}.
                              {t('katana.routing_legend_wildcard')} <code className="text-shogun-blue font-mono">*</code> {t('katana.routing_legend_catch')}.
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            </div>}
          </div>
        )}

        {/* ══ TELEGRAM TAB ══════════════════════════════════════════ */}
        {activeTab === 'teams' && <MicrosoftTeamsAdapterTab />}

        {activeTab === 'telegram' && (
          <div className="space-y-6 animate-in fade-in duration-300">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                  <MessageCircle className="w-5 h-5 text-shogun-blue" /> {t('katana.telegram_channel')}
                </h3>
                <p className="text-xs text-shogun-subdued mt-1">{t('katana.telegram_desc')}</p>
              </div>
              {tgStatus?.connected && (
                <div className="flex items-center gap-2 px-3 py-1.5 bg-green-400/10 border border-green-400/30 rounded-lg">
                  <Wifi className="w-3.5 h-3.5 text-green-400" />
                  <span className="text-xs font-bold text-green-400">{t('katana.connected')}</span>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
              {/* Left: form */}
              <div className="lg:col-span-3 space-y-5">

                {tgStatus?.connected && (
                  <div className="shogun-card bg-green-400/5 border-green-400/20 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-xl bg-green-400/10 border border-green-400/30 flex items-center justify-center">
                        <MessageCircle className="w-6 h-6 text-green-400" />
                      </div>
                      <div>
                        <p className="font-bold text-shogun-text">@{tgStatus.bot_username}</p>
                        <p className="text-[10px] text-shogun-subdued mt-0.5">Bot ID: {tgStatus.bot_id} · {tgStatus.first_name}</p>
                        <p className="text-[10px] text-shogun-subdued">
                          {t('katana.mode')}: <span className="font-bold uppercase text-green-400">{tgStatus.mode}</span>
                          {tgStatus.last_connected_at && <> · {new Date(tgStatus.last_connected_at).toLocaleDateString()}</>}
                        </p>
                      </div>
                    </div>
                    <button onClick={handleTgDisconnect}
                      className="flex items-center gap-1.5 px-3 py-1.5 border border-red-400/30 text-red-400/70 hover:text-red-400 hover:border-red-400/50 rounded-lg text-xs font-bold transition-all">
                      <WifiOff className="w-3.5 h-3.5" /> {t('katana.disconnect')}
                    </button>
                  </div>
                )}

                <div className="shogun-card space-y-5">
                  <h4 className="text-sm font-bold text-shogun-text">
                    {tgStatus?.connected ? t('katana.update_configuration') : t('katana.connect_a_bot')}
                  </h4>
                  <form onSubmit={handleTgConnect} className="space-y-4">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-1.5">
                        <ShieldCheck className="w-3 h-3 text-shogun-gold" /> {t('katana.bot_token')}
                      </label>
                      <div className="relative">
                        <input type={tgShowToken ? 'text' : 'password'} required
                          placeholder={tgStatus?.connected ? 'Enter new token to re-connect…' : '123456789:AAExxxxxxxx'}
                          value={tgToken} onChange={e => setTgToken(e.target.value)}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 pr-10 text-sm focus:border-shogun-blue outline-none font-mono" />
                        <button type="button" onClick={() => setTgShowToken(v => !v)}
                          className="absolute right-3 top-1/2 -translate-y-1/2 text-shogun-subdued hover:text-shogun-text">
                          {tgShowToken ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                        </button>
                      </div>
                      <p className="text-[9px] text-shogun-subdued/60">
                        {t('katana.get_token_from')} <a href="https://t.me/BotFather" target="_blank" rel="noreferrer" className="text-shogun-blue hover:underline">@BotFather</a>.
                      </p>
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.update_mode', 'Update Mode')}</label>
                      <div className="flex gap-2">
                        {(['polling', 'webhook'] as const).map(m => (
                          <button key={m} type="button" onClick={() => setTgMode(m)}
                            className={cn('flex-1 py-2 rounded-lg border text-xs font-bold uppercase tracking-widest transition-all',
                              tgMode === m ? 'bg-shogun-blue text-white border-shogun-blue' : 'border-shogun-border text-shogun-subdued hover:border-shogun-blue/40')}>
                            {m === 'polling' ? t('katana.polling') : t('katana.webhook')}
                          </button>
                        ))}
                      </div>
                      <p className="text-[9px] text-shogun-subdued/60">
                        {tgMode === 'polling' ? t('katana.polling_desc') : t('katana.webhook_desc')}
                      </p>
                    </div>

                    {tgMode === 'webhook' && (
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.webhook_url', 'Webhook URL *')}</label>
                        <input type="url" required placeholder="https://yourdomain.com/telegram/webhook"
                          value={tgWebhook} onChange={e => setTgWebhook(e.target.value)}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none font-mono" />
                      </div>
                    )}

                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-1.5">
                        <Shield className="w-3 h-3 text-shogun-gold" /> {t('katana.allowed_chat_ids')}
                        <span className="font-normal normal-case tracking-normal text-shogun-subdued/50">({t('katana.optional_whitelist')})</span>
                      </label>
                      <input type="text" placeholder="e.g. 123456789, -987654321"
                        value={tgChatIds} onChange={e => setTgChatIds(e.target.value)}
                        className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none font-mono" />
                      <p className="text-[9px] text-shogun-subdued/60">{t('katana.chat_ids_help')}</p>
                    </div>

                    <button type="submit" disabled={tgSaving || !tgToken.trim()}
                      className="w-full flex items-center justify-center gap-2 py-3 bg-shogun-blue hover:bg-shogun-blue/90 disabled:opacity-40 text-white font-bold rounded-lg text-sm transition-all">
                      {tgSaving
                        ? <><RefreshCw className="w-4 h-4 animate-spin" /> {t('katana.connecting')}</>
                        : <><MessageCircle className="w-4 h-4" /> {tgStatus?.connected ? t('katana.update_connection') : t('katana.connect_bot')}</>}
                    </button>
                  </form>
                </div>
              </div>

              {/* Right: test + guide */}
              <div className="lg:col-span-2 space-y-5">
                <div className="shogun-card space-y-4">
                  <h4 className="text-sm font-bold text-shogun-text flex items-center gap-2">
                    <Send className="w-4 h-4 text-shogun-blue" /> {t('katana.test_connection')}
                  </h4>
                  {!tgStatus?.connected
                    ? <p className="text-center py-6 text-shogun-subdued text-xs italic">{t('katana.connect_bot_first')}</p>
                    : (
                      <div className="space-y-3">
                        <input type="text" placeholder="Your chat ID, e.g. 123456789"
                          value={tgTestChat} onChange={e => setTgTestChat(e.target.value)}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue outline-none font-mono" />
                        <button onClick={handleTgTest} disabled={tgTesting || !tgTestChat.trim()}
                          className="w-full flex items-center justify-center gap-2 py-2.5 border border-shogun-blue/40 bg-shogun-blue/10 hover:bg-shogun-blue/20 text-shogun-blue disabled:opacity-40 font-bold rounded-lg text-sm transition-all">
                          {tgTesting ? <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> {t('katana.sending')}</> : <><Send className="w-3.5 h-3.5" /> {t('katana.send_test')}</>}
                        </button>
                        {tgTestResult && (
                          <div className={cn('p-3 rounded-lg text-xs flex items-start gap-2',
                            tgTestResult.ok ? 'bg-green-400/10 border border-green-400/20 text-green-400' : 'bg-red-400/10 border border-red-400/20 text-red-400')}>
                            {tgTestResult.ok ? <Check className="w-3.5 h-3.5 shrink-0 mt-0.5" /> : <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />}
                            {tgTestResult.message || tgTestResult.error}
                          </div>
                        )}
                      </div>
                    )
                  }
                </div>

                <div className="shogun-card space-y-4">
                  <h4 className="text-sm font-bold text-shogun-text flex items-center gap-2">
                    <ChevronRight className="w-4 h-4 text-shogun-gold" /> {t('katana.quick_setup')}
                  </h4>
                  <ol className="space-y-3">
                    {[
                      { n: '1', t: t('katana.tg_step1'), href: 'https://t.me/BotFather' },
                      { n: '2', t: t('katana.tg_step2') },
                      { n: '3', t: t('katana.tg_step3') },
                      { n: '4', t: t('katana.tg_step4') },
                      { n: '5', t: t('katana.tg_step5') },
                    ].map(({ n, t, href }) => (
                      <li key={n} className="flex items-start gap-3">
                        <span className="w-5 h-5 rounded-full bg-shogun-blue/20 border border-shogun-blue/40 text-shogun-blue text-[9px] font-bold flex items-center justify-center shrink-0 mt-0.5">{n}</span>
                        <span className="text-xs text-shogun-subdued leading-relaxed">
                          {t}{href && <> — <a href={href} target="_blank" rel="noreferrer" className="text-shogun-blue hover:underline">{href.split('//')[1]}</a></>}
                        </span>
                      </li>
                    ))}
                  </ol>
                  <div className="pt-2 border-t border-shogun-border mt-3">
                    <button onClick={handleTgDetect} disabled={tgDetecting}
                      className="w-full flex items-center justify-center gap-2 py-2 border border-shogun-gold/30 bg-shogun-gold/10 hover:bg-shogun-gold/20 text-shogun-gold disabled:opacity-40 font-bold rounded-lg text-xs transition-all">
                      {tgDetecting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
                      {t('katana.auto_detect_chat_id')}
                    </button>
                    <p className="text-[10px] text-shogun-subdued text-center mt-2 leading-tight">{t('katana.must_complete_step5')} <br/>{t('katana.auto_whitelist_desc')}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ══ MAIL & CALENDAR TAB ═══════════════════════════════════ */}
        {activeTab === 'telegram' && tgTopicGroups.length > 0 && (
          <div className="shogun-card space-y-4 mt-6">
            <div>
              <h4 className="text-sm font-bold text-shogun-text flex items-center gap-2">
                <MessageCircle className="w-4 h-4 text-sky-400" /> Forum Topic Mapping
              </h4>
              <p className="text-[10px] text-shogun-subdued mt-1">
                Thread IDs are captured automatically. Name older topics here, or send <b>*strategy</b>, <b>*research</b>, <b>*shogun</b>, <b>*personal</b>, <b>*education</b>, <b>*general</b>, or <b>*news</b> inside a topic to teach Shogun automatically.
              </p>
            </div>
            {tgTopicGroups.map((group: any) => (
              <div key={group.chat_id} className="rounded-lg border border-shogun-border bg-[#050508] p-3 space-y-3">
                <div className="flex items-center justify-between text-xs">
                  <b>{group.chat_title || 'Telegram group'}</b>
                  <span className="font-mono text-[9px] text-shogun-subdued">{group.chat_id}</span>
                </div>
                {(group.topics || []).length === 0 ? (
                  <p className="text-[10px] text-shogun-subdued">No forum threads observed yet. Send one message in each topic.</p>
                ) : (group.topics || []).map((topic: any) => {
                  const key = `${group.chat_id}:${topic.message_thread_id}`;
                  return (
                    <div key={key} className="grid grid-cols-[90px_minmax(0,1fr)_90px] items-center gap-2">
                      <span className="text-[10px] font-mono text-sky-400">Thread {topic.message_thread_id}</span>
                      <input
                        value={tgTopicDrafts[key] || ''}
                        onChange={event => setTgTopicDrafts(prev => ({ ...prev, [key]: event.target.value }))}
                        placeholder="Enter topic name"
                        className="w-full bg-shogun-bg border border-shogun-border rounded-lg px-3 py-2 text-xs focus:border-sky-400 outline-none"
                      />
                      <button
                        onClick={() => handleSaveTgTopic(group.chat_id, topic.message_thread_id)}
                        disabled={tgTopicSaving === key || !(tgTopicDrafts[key] || '').trim()}
                        className="rounded-lg border border-sky-400/30 bg-sky-400/10 px-3 py-2 text-[10px] font-bold text-sky-300 disabled:opacity-40"
                      >
                        {tgTopicSaving === key ? 'SAVING' : 'SAVE'}
                      </button>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        )}

        {activeTab === 'mail_calendar' && (
          <div className="space-y-6 animate-in fade-in duration-300">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                  <Mail className="w-5 h-5 text-shogun-blue" /> {t('katana.mail_calendar_settings', 'Mail & Calendar Settings')}
                </h3>
                <p className="text-xs text-shogun-subdued mt-1">
                  {t('katana.mail_calendar_desc', 'Configure a single email and calendar account to send/receive mail and manage events.')}
                </p>
              </div>
              {mailAccount?.is_active && (
                <div className="flex items-center gap-2 px-3 py-1.5 bg-green-400/10 border border-green-400/30 rounded-lg">
                  <Wifi className="w-3.5 h-3.5 text-green-400" />
                  <span className="text-xs font-bold text-green-400">{t('katana.connected', 'Connected')}</span>
                </div>
              )}
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
              {/* Left Column: Connection Info & Form */}
              <div className="lg:col-span-3 space-y-5">
                {mailAccount?.is_active && (
                  <div className="shogun-card bg-green-400/5 border-green-400/20 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-xl bg-green-400/10 border border-green-400/30 flex items-center justify-center">
                        <Mail className="w-6 h-6 text-green-400" />
                      </div>
                      <div>
                        <p className="font-bold text-shogun-text">{mailAccount.display_name || mailAccount.email_address}</p>
                        <p className="text-[10px] text-shogun-subdued mt-0.5">
                          {mailAccount.email_address} · {mailAccount.provider.toUpperCase()}
                        </p>
                        <p className="text-[10px] text-shogun-subdued">
                          {t('katana.calendar_integrated', 'Calendar')}: <span className="font-bold uppercase text-green-400">{mailAccount.calendar_provider}</span>
                        </p>
                      </div>
                    </div>
                    <button
                      onClick={handleMailDisconnect}
                      className="flex items-center gap-1.5 px-3 py-1.5 border border-red-400/30 text-red-400/70 hover:text-red-400 hover:border-red-400/50 rounded-lg text-xs font-bold transition-all"
                    >
                      <WifiOff className="w-3.5 h-3.5" /> {t('katana.disconnect', 'Disconnect')}
                    </button>
                  </div>
                )}

                <div className="shogun-card space-y-5">
                  <h4 className="text-sm font-bold text-shogun-text">
                    {mailAccount?.is_active ? t('katana.update_mail_config', 'Update Connection Settings') : t('katana.connect_mail_account', 'Connect Email Account')}
                  </h4>
                  <form onSubmit={handleMailConnect} className="space-y-4">
                    {/* Provider Select */}
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.mail_provider', 'Provider')}</label>
                      <select
                        value={mailForm.provider}
                        onChange={e => setMailForm({ ...mailForm, provider: e.target.value })}
                        className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none text-shogun-text"
                      >
                        <option value="gmail">Google Gmail</option>
                        <option value="outlook">Microsoft Outlook</option>
                        <option value="proton">Proton Mail (Bridge)</option>
                        <option value="other">Other / Custom IMAP</option>
                      </select>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      {/* Display Name */}
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.display_name', 'Display Name')}</label>
                        <input
                          type="text"
                          required
                          placeholder="e.g. Shogun Agent"
                          value={mailForm.display_name}
                          onChange={e => setMailForm({ ...mailForm, display_name: e.target.value })}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                        />
                      </div>
                      {/* Email Address */}
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.email_address', 'Email Address')}</label>
                        <input
                          type="email"
                          required
                          placeholder="e.g. user@domain.com"
                          value={mailForm.email_address}
                          onChange={e => setMailForm({ ...mailForm, email_address: e.target.value, username: mailForm.username || e.target.value })}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                        />
                      </div>
                    </div>

                    {/* IMAP/POP3 Section */}
                    <div className="pt-4 border-t border-shogun-border/40 space-y-4">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-shogun-text uppercase tracking-wider">{t('katana.incoming_mail_server', 'Incoming Mail Server')}</span>
                        <div className="flex gap-2">
                          {(['imap', 'pop3'] as const).map(p => (
                            <button
                              key={p}
                              type="button"
                              onClick={() => setMailForm({ ...mailForm, protocol: p })}
                              className={cn(
                                'px-3 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider border transition-all',
                                mailForm.protocol === p ? 'bg-shogun-blue text-white border-shogun-blue' : 'border-shogun-border text-shogun-subdued hover:border-shogun-blue/40'
                              )}
                            >
                              {p.toUpperCase()}
                            </button>
                          ))}
                        </div>
                      </div>

                      <div className="grid grid-cols-3 gap-4">
                        <div className="col-span-2 space-y-1.5">
                          <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.incoming_host', 'Host')}</label>
                          <input
                            type="text"
                            required
                            placeholder="imap.example.com"
                            value={mailForm.imap_host}
                            onChange={e => setMailForm({ ...mailForm, imap_host: e.target.value })}
                            className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none font-mono"
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.incoming_port', 'Port')}</label>
                          <input
                            type="number"
                            required
                            value={mailForm.imap_port}
                            onChange={e => setMailForm({ ...mailForm, imap_port: parseInt(e.target.value) || 0 })}
                            className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none font-mono"
                          />
                        </div>
                      </div>

                      <label className="flex items-center gap-2 cursor-pointer text-xs text-shogun-subdued hover:text-shogun-text transition-colors">
                        <input
                          type="checkbox"
                          checked={mailForm.imap_use_ssl}
                          onChange={e => setMailForm({ ...mailForm, imap_use_ssl: e.target.checked })}
                          className="accent-shogun-blue"
                        />
                        {t('katana.incoming_ssl', 'Use SSL/TLS for Incoming Mail')}
                      </label>
                    </div>

                    {/* SMTP Section */}
                    <div className="pt-4 border-t border-shogun-border/40 space-y-4">
                      <span className="text-xs font-bold text-shogun-text uppercase tracking-wider block">{t('katana.outgoing_mail_server', 'Outgoing SMTP Server')}</span>

                      <div className="grid grid-cols-3 gap-4">
                        <div className="col-span-2 space-y-1.5">
                          <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.outgoing_host', 'Host')}</label>
                          <input
                            type="text"
                            required
                            placeholder="smtp.example.com"
                            value={mailForm.smtp_host}
                            onChange={e => setMailForm({ ...mailForm, smtp_host: e.target.value })}
                            className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none font-mono"
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.outgoing_port', 'Port')}</label>
                          <input
                            type="number"
                            required
                            value={mailForm.smtp_port}
                            onChange={e => setMailForm({ ...mailForm, smtp_port: parseInt(e.target.value) || 0 })}
                            className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none font-mono"
                          />
                        </div>
                      </div>

                      <label className="flex items-center gap-2 cursor-pointer text-xs text-shogun-subdued hover:text-shogun-text transition-colors">
                        <input
                          type="checkbox"
                          checked={mailForm.smtp_use_ssl}
                          onChange={e => setMailForm({ ...mailForm, smtp_use_ssl: e.target.checked })}
                          className="accent-shogun-blue"
                        />
                        {t('katana.outgoing_ssl', 'Use SSL/TLS for Outgoing Mail')}
                      </label>
                    </div>

                    {/* Authentication Section */}
                    <div className="pt-4 border-t border-shogun-border/40 space-y-4">
                      <span className="text-xs font-bold text-shogun-text uppercase tracking-wider block">{t('katana.auth', 'Authentication')}</span>

                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.username', 'Username')}</label>
                          <input
                            type="text"
                            required
                            placeholder="e.g. user@domain.com"
                            value={mailForm.username}
                            onChange={e => setMailForm({ ...mailForm, username: e.target.value })}
                            className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                          />
                        </div>
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center justify-between">
                            <span>{t('katana.password', 'Password')}</span>
                          </label>
                          <div className="relative">
                            <input
                              type={showMailPassword ? 'text' : 'password'}
                              required={!mailAccount}
                              placeholder={mailAccount ? '••••••••' : 'Password or App Password'}
                              value={mailForm.password}
                              onChange={e => setMailForm({ ...mailForm, password: e.target.value })}
                              className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 pr-10 text-sm focus:border-shogun-blue outline-none font-mono"
                            />
                            <button
                              type="button"
                              onClick={() => setShowMailPassword(v => !v)}
                              className="absolute right-3 top-1/2 -translate-y-1/2 text-shogun-subdued hover:text-shogun-text"
                            >
                              {showMailPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Calendar Integration Section */}
                    <div className="pt-4 border-t border-shogun-border/40 space-y-4">
                      <span className="text-xs font-bold text-shogun-text uppercase tracking-wider block">{t('katana.calendar_integration', 'Calendar Integration')}</span>

                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-1.5">
                          <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.calendar_provider', 'Provider')}</label>
                          <select
                            value={mailForm.calendar_provider}
                            onChange={e => setMailForm({ ...mailForm, calendar_provider: e.target.value })}
                            className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none text-shogun-text"
                          >
                            <option value="none">None / Disabled</option>
                            <option value="caldav">CalDAV (Proton / Generic)</option>
                            <option value="google_api">Google Calendar API</option>
                            <option value="microsoft_graph">Microsoft Graph</option>
                          </select>
                        </div>

                        {mailForm.calendar_provider === 'caldav' && (
                          <div className="space-y-1.5">
                            <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">{t('katana.caldav_url', 'CalDAV URL')}</label>
                            <input
                              type="url"
                              required
                              placeholder="https://caldav.example.com"
                              value={mailForm.caldav_url}
                              onChange={e => setMailForm({ ...mailForm, caldav_url: e.target.value })}
                              className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none font-mono"
                            />
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Connection Test Results */}
                    {mailTestResult && (
                      <div className={cn(
                        'p-4 rounded-lg text-xs space-y-2 border',
                        mailTestResult.ok
                          ? 'bg-green-400/10 border-green-400/20 text-green-400'
                          : 'bg-red-400/10 border-red-400/20 text-red-400'
                      )}>
                        <div className="flex items-center gap-2 font-bold">
                          {mailTestResult.ok ? <Check className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                          <span>{mailTestResult.ok ? t('katana.test_successful', 'All connections successful!') : t('katana.test_failed', 'Connection tests failed')}</span>
                        </div>
                        <p className="text-[10px] leading-relaxed opacity-90">{mailTestResult.message}</p>
                        <div className="flex gap-4 pt-1 text-[10px]">
                          <span className="flex items-center gap-1">
                            <span className={cn('w-1.5 h-1.5 rounded-full', mailTestResult.imap_ok ? 'bg-green-400' : 'bg-red-400')} />
                            Incoming Server Login: {mailTestResult.imap_ok ? 'OK' : 'FAIL'}
                          </span>
                          <span className="flex items-center gap-1">
                            <span className={cn('w-1.5 h-1.5 rounded-full', mailTestResult.smtp_ok ? 'bg-green-400' : 'bg-red-400')} />
                            Outgoing SMTP Login: {mailTestResult.smtp_ok ? 'OK' : 'FAIL'}
                          </span>
                        </div>
                      </div>
                    )}

                    <div className="flex gap-4 pt-2">
                      <button
                        type="button"
                        onClick={handleMailTest}
                        disabled={mailTesting || !mailForm.email_address || !mailForm.username}
                        className="flex-1 flex items-center justify-center gap-2 py-3 border border-shogun-blue/40 bg-shogun-blue/10 hover:bg-shogun-blue/20 text-shogun-blue disabled:opacity-40 font-bold rounded-lg text-sm transition-all"
                      >
                        {mailTesting ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                        {t('katana.test_connection', 'Test Connection')}
                      </button>

                      <button
                        type="submit"
                        disabled={mailSaving || !mailForm.email_address || !mailForm.username}
                        className="flex-1 flex items-center justify-center gap-2 py-3 bg-shogun-blue hover:bg-shogun-blue/90 disabled:opacity-40 text-white font-bold rounded-lg text-sm transition-all"
                      >
                        {mailSaving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        {mailAccount?.is_active ? t('katana.save_settings', 'Save Settings') : t('katana.connect_account', 'Connect Account')}
                      </button>
                    </div>
                  </form>
                </div>
              </div>

              {/* Right Column: Setup guides */}
              <div className="lg:col-span-2 space-y-5">
                {/* Setup Guides */}
                <div className="shogun-card space-y-4">
                  <h4 className="text-sm font-bold text-shogun-text flex items-center gap-2">
                    <ChevronRight className="w-4 h-4 text-shogun-gold" />
                    {t('katana.setup_guides', 'Quick Setup Guide')}
                  </h4>

                  <div className="text-xs space-y-4">
                    {mailForm.provider === 'gmail' && (
                      <div className="space-y-2 animate-in fade-in duration-200">
                        <h5 className="font-bold text-shogun-blue">Google Gmail Setup:</h5>
                        <ol className="list-decimal pl-4 space-y-1.5 text-shogun-subdued text-[11px] leading-relaxed">
                          <li>Go to your Google Account settings &rarr; Security.</li>
                          <li>Ensure <strong>2-Step Verification</strong> is enabled.</li>
                          <li>Click on <strong>App passwords</strong> (or search for it).</li>
                          <li>Generate a new app password for "Mail" on your device.</li>
                          <li>Use your Gmail address as username and the 16-character generated password to connect.</li>
                        </ol>
                      </div>
                    )}

                    {mailForm.provider === 'outlook' && (
                      <div className="space-y-2 animate-in fade-in duration-200">
                        <h5 className="font-bold text-shogun-blue">Outlook / Office 365 Setup:</h5>
                        <ol className="list-decimal pl-4 space-y-1.5 text-shogun-subdued text-[11px] leading-relaxed">
                          <li>Log in to your Outlook Account security settings.</li>
                          <li>Select <strong>Manage how I sign in</strong> &rarr; App passwords.</li>
                          <li>Create a new App Password.</li>
                          <li>Use your Outlook email address and the App Password to connect.</li>
                          <li>For Exchange accounts, verify IMAP access is enabled in Outlook settings.</li>
                        </ol>
                      </div>
                    )}

                    {mailForm.provider === 'proton' && (
                      <div className="space-y-2 animate-in fade-in duration-200">
                        <h5 className="font-bold text-shogun-blue">Proton Mail (Bridge) Setup:</h5>
                        <ol className="list-decimal pl-4 space-y-1.5 text-shogun-subdued text-[11px] leading-relaxed">
                          <li>Download and open the <strong>Proton Mail Bridge</strong> application.</li>
                          <li>Add your Proton account to the Bridge and wait for local encryption to sync.</li>
                          <li>Go to Bridge settings to view the local IMAP port, SMTP port, and Bridge password.</li>
                          <li>Set host to <code className="text-shogun-blue font-mono bg-[#050508] px-1 rounded">127.0.0.1</code>.</li>
                          <li>Use the ports provided by the Bridge (default: IMAP 1143, SMTP 1025) and disable SSL/TLS toggles (the Bridge encrypts traffic locally).</li>
                        </ol>
                      </div>
                    )}

                    {mailForm.provider === 'other' && (
                      <div className="space-y-2 animate-in fade-in duration-200">
                        <h5 className="font-bold text-shogun-blue">Generic Mail Provider:</h5>
                        <p className="text-[11px] text-shogun-subdued leading-relaxed">
                          Enter your custom IMAP and SMTP server details (hostnames, ports, and SSL settings) as provided by your email provider. Ensure your credentials are correct.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════════════════════
            OFFICE TAB
        ════════════════════════════════════════════════════════ */}
        {activeTab === 'office' && (
          <div className="space-y-6">
            {officePosture === 'shrine' && (
              <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-5 flex items-center gap-4">
                <AlertCircle className="w-6 h-6 text-red-400 flex-shrink-0" />
                <div>
                  <h3 className="text-sm font-bold text-red-400">Office Disabled at SHRINE Posture</h3>
                  <p className="text-xs text-shogun-subdued mt-1">Office App Mode is blocked at SHRINE security tier. Raise your posture in Torii to at least GUARDED to use Office automation.</p>
                </div>
              </div>
            )}

            <div className={cn(officePosture === 'shrine' && 'opacity-40 pointer-events-none select-none')}>
              {/* Master Enable */}
              {officeConfig && (
                <div className={cn(
                  "rounded-xl border p-5 transition-all duration-500 mb-6",
                  officeConfig.enabled
                    ? "border-green-500/40 bg-gradient-to-r from-[#0f1422] to-[#131926] shadow-xl shadow-green-500/10"
                    : "border-shogun-border bg-shogun-card"
                )}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className={cn(
                        "p-3 rounded-xl transition-colors duration-500",
                        officeConfig.enabled ? "bg-green-500/15 text-green-400" : "bg-shogun-bg text-shogun-subdued"
                      )}>
                        <Power className="w-6 h-6" />
                      </div>
                      <div>
                        <h2 className="text-lg font-semibold text-shogun-text">Office App Mode</h2>
                        <p className="text-xs text-shogun-subdued mt-0.5">
                          {officeConfig.enabled ? 'Active — AI agents can interact with Office applications' : 'Disabled — Enable to allow Office automation'}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      {officeUnsaved && <span className="text-xs text-amber-400 animate-pulse">Unsaved</span>}
                      <button onClick={saveOfficeConfig} disabled={officeSaving || !officeUnsaved}
                        className={cn("flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all",
                          officeUnsaved ? "bg-shogun-gold text-black hover:bg-[#e6b422] shadow-lg shadow-shogun-gold/20" : "bg-shogun-border text-shogun-subdued cursor-not-allowed"
                        )}>
                        {officeSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />} Save
                      </button>
                      <button onClick={() => updateOfficeConfig('enabled', !officeConfig.enabled)}
                        className={cn("relative w-14 h-7 rounded-full transition-all duration-500", officeConfig.enabled ? "bg-green-500" : "bg-shogun-border")}>
                        <span className={cn("absolute top-1 w-5 h-5 rounded-full bg-white shadow-lg transition-transform duration-500", officeConfig.enabled ? "translate-x-8 left-0" : "left-1")} />
                      </button>
                    </div>
                  </div>
                  {!officeStatus?.platform_supported && (
                    <div className="mt-3 flex items-center gap-2 text-xs text-amber-400 bg-amber-500/10 rounded-lg p-3">
                      <AlertCircle className="w-4 h-4 flex-shrink-0" />
                      <span>{officeStatus?.message || 'Office App Mode requires Windows with Microsoft Office installed.'}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Applications */}
              {officeStatus && officeConfig && (
                <div className="space-y-3 mb-6">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-shogun-subdued uppercase tracking-wider">Applications</h2>
                    <button onClick={detectOfficeApps} disabled={officeDetecting}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-shogun-subdued bg-shogun-bg hover:bg-shogun-border border border-shogun-border transition-all">
                      <RefreshCw className={cn("w-3.5 h-3.5", officeDetecting && "animate-spin")} /> Re-detect
                    </button>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                    {[
                      { app: officeStatus.excel, key: 'excel', icon: FileSpreadsheet, color: 'text-green-400', label: 'Excel' },
                      { app: officeStatus.word, key: 'word', icon: FileText, color: 'text-blue-400', label: 'Word' },
                      { app: officeStatus.powerpoint, key: 'powerpoint', icon: Layers, color: 'text-orange-400', label: 'PowerPoint' },
                      { app: officeStatus.outlook, key: 'outlook', icon: Mail, color: 'text-cyan-400', label: 'Outlook' },
                    ].map(({ app, key, icon: Icon, color, label }) => (
                      <div key={key} className={cn(
                        "relative rounded-xl border p-5 transition-all duration-300",
                        app?.installed && officeConfig[key]?.enabled
                          ? "border-shogun-gold/30 bg-shogun-card shadow-lg shadow-shogun-gold/5"
                          : "border-shogun-border bg-shogun-bg/60 opacity-70"
                      )}>
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-3">
                            <div className={cn("p-2.5 rounded-lg bg-shogun-bg", color)}><Icon className="w-5 h-5" /></div>
                            <div>
                              <h3 className="text-sm font-semibold text-shogun-text">{label}</h3>
                              {app?.version && <p className="text-xs text-shogun-subdued mt-0.5">v{app.version}</p>}
                            </div>
                          </div>
                          <button onClick={() => updateOfficeConfig(`${key}.enabled`, !officeConfig[key]?.enabled)}
                            disabled={!app?.installed}
                            className={cn("relative w-10 h-5 rounded-full transition-all duration-300",
                              officeConfig[key]?.enabled && app?.installed ? "bg-shogun-gold" : "bg-shogun-border",
                              !app?.installed && "opacity-40 cursor-not-allowed"
                            )}>
                            <span className={cn("absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-md transition-transform duration-300",
                              officeConfig[key]?.enabled && app?.installed ? "translate-x-5 left-0.5" : "left-0.5"
                            )} />
                          </button>
                        </div>
                        <div className="flex gap-2 flex-wrap">
                          <span className={cn("inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium tracking-wide",
                            app?.installed ? "bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30" : "bg-red-500/15 text-red-400 ring-1 ring-red-500/30"
                          )}>
                            {app?.installed ? <CheckCircle2 className="w-3.5 h-3.5" /> : <X className="w-3.5 h-3.5" />}
                            {app?.installed ? 'Installed' : 'Not found'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Folders */}
              {officeConfig && (
                <div className="shogun-card space-y-4 mb-6">
                  <div className="font-bold text-shogun-text flex items-center gap-2"><FolderOpen className="w-4 h-4 text-shogun-gold" /> Approved Folders</div>
                  <p className="text-xs text-shogun-subdued">All file operations are restricted to these folders. Files outside these boundaries will be rejected. By default, these map to subdirectories inside the <span className="text-shogun-gold font-medium">Agent Workspace</span>.</p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {['input', 'output', 'templates', 'temp'].map(folder => (
                      <div key={folder}>
                        <label className="block text-xs font-medium text-shogun-subdued mb-1.5 capitalize">{folder}</label>
                        <div className="flex items-center gap-2">
                          <Folder className="w-4 h-4 text-shogun-subdued flex-shrink-0" />
                          <input type="text" value={officeConfig.folders?.[folder] || ''}
                            onChange={e => updateOfficeConfig(`folders.${folder}`, e.target.value)}
                            placeholder={`workspace/${folder}`}
                            className="flex-1 bg-shogun-bg border border-shogun-border rounded-lg px-3 py-2 text-sm text-shogun-text placeholder-shogun-subdued/40 focus:outline-none focus:border-shogun-gold/50 transition-colors font-mono" />
                        </div>
                      </div>
                    ))}
                  </div>
                  <div className="bg-shogun-blue/5 border border-shogun-blue/20 rounded-lg p-3 flex items-start gap-2">
                    <FileText className="w-4 h-4 text-shogun-blue flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-shogun-subdued">Leave paths empty to auto-map to the <span className="text-shogun-blue font-medium">Workspace</span> root folder (data/workspace). The Workspace is shared between Shogun, Samurai, and the File Explorer in Comms.</p>
                  </div>
                </div>
              )}

              {/* Safety */}
              {officeConfig && (
                <div className="shogun-card space-y-4 mb-6">
                  <div className="font-bold text-shogun-text flex items-center gap-2"><Shield className="w-4 h-4 text-shogun-gold" /> Safety &amp; Security</div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {[
                      { key: 'safety.block_path_traversal', label: 'Block path traversal', desc: 'Prevent ../ escape attacks' },
                      { key: 'safety.block_shortcuts', label: 'Block .lnk files', desc: 'Prevent shortcut escape' },
                      { key: 'safety.block_unc_paths', label: 'Block UNC paths', desc: 'Prevent network path access' },
                      { key: 'safety.version_outputs', label: 'Version outputs', desc: 'Auto-timestamp output files' },
                      { key: 'safety.require_output_validation', label: 'Validate outputs', desc: 'Verify output file integrity' },
                      { key: 'temp_cleanup_on_startup', label: 'Cleanup temp on startup', desc: 'Remove temp files at boot' },
                    ].map(item => {
                      const keys = item.key.split('.');
                      const val = keys.length === 2 ? officeConfig[keys[0]]?.[keys[1]] : officeConfig[keys[0]];
                      return (
                        <label key={item.key} className="flex items-start gap-3 p-3 rounded-lg bg-shogun-bg border border-shogun-border cursor-pointer hover:border-shogun-gold/20 transition-colors">
                          <input type="checkbox" checked={!!val} onChange={() => updateOfficeConfig(item.key, !val)} className="mt-0.5 accent-[#d4a017]" />
                          <div>
                            <p className="text-sm text-shogun-text font-medium">{item.label}</p>
                            <p className="text-xs text-shogun-subdued mt-0.5">{item.desc}</p>
                          </div>
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Outlook */}
              {officeConfig && (
                <div className="shogun-card space-y-4">
                  <div className="font-bold text-shogun-text flex items-center gap-2"><Mail className="w-4 h-4 text-cyan-400" /> Outlook Settings</div>
                  <div>
                    <label className="block text-xs font-medium text-shogun-subdued mb-2">Outlook Mode</label>
                    <div className="flex gap-3">
                      {[
                        { value: 'draft_only', label: 'Draft Only', desc: 'Create drafts, never send' },
                        { value: 'confirmed_send', label: 'Confirmed Send', desc: 'Send with approval' },
                        { value: 'approved_recipient_send', label: 'Approved Recipients', desc: 'Auto-send to allowlist' },
                      ].map(mode => (
                        <button key={mode.value} onClick={() => updateOfficeConfig('outlook.mode', mode.value)}
                          className={cn("flex-1 p-3 rounded-lg border text-left transition-all",
                            officeConfig.outlook?.mode === mode.value
                              ? "border-shogun-gold/50 bg-shogun-gold/10"
                              : "border-shogun-border bg-shogun-bg hover:border-shogun-gold/20"
                          )}>
                          <p className={cn("text-sm font-medium", officeConfig.outlook?.mode === mode.value ? "text-shogun-gold" : "text-shogun-text")}>{mode.label}</p>
                          <p className="text-xs text-shogun-subdued mt-0.5">{mode.desc}</p>
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <label className="flex items-start gap-3 p-3 rounded-lg bg-shogun-bg border border-shogun-border cursor-pointer hover:border-shogun-gold/20 transition-colors">
                      <input type="checkbox" checked={!!officeConfig.outlook?.require_confirmation}
                        onChange={() => updateOfficeConfig('outlook.require_confirmation', !officeConfig.outlook?.require_confirmation)} className="mt-0.5 accent-[#d4a017]" />
                      <div>
                        <p className="text-sm text-shogun-text font-medium">Require confirmation</p>
                        <p className="text-xs text-shogun-subdued mt-0.5">Human must approve before sending</p>
                      </div>
                    </label>
                    <label className="flex items-start gap-3 p-3 rounded-lg bg-shogun-bg border border-shogun-border cursor-pointer hover:border-shogun-gold/20 transition-colors">
                      <input type="checkbox" checked={!!officeConfig.outlook?.allow_external_recipients}
                        onChange={() => updateOfficeConfig('outlook.allow_external_recipients', !officeConfig.outlook?.allow_external_recipients)} className="mt-0.5 accent-[#d4a017]" />
                      <div>
                        <p className="text-sm text-shogun-text font-medium">Allow external recipients</p>
                        <p className="text-xs text-shogun-subdued mt-0.5">Send to domains outside the allowlist</p>
                      </div>
                    </label>
                  </div>
                </div>
              )}

              {!officeStatus && !officeConfig && (
                <div className="flex items-center justify-center h-40">
                  <Loader2 className="w-6 h-6 text-shogun-gold animate-spin" />
                </div>
              )}
            </div>
          </div>
        )}

        {/* ════════════════════════════════════════════════════════
            MADO TAB
        ════════════════════════════════════════════════════════ */}
        {activeTab === 'mado' && (
          <div className="animate-in fade-in duration-300">
            <Mado />
          </div>
        )}

        {activeTab === 'ide' && <IdeModeTab />}

        {/* ════════════════════════════════════════════════════════
            RONIN TAB
        ════════════════════════════════════════════════════════ */}
        {activeTab === 'ronin' && (
          <div className="animate-in fade-in duration-300">
            <Ronin />
          </div>
        )}

        {/* ════════════════════════════════════════════════════════
            SKILLOPT TAB
        ════════════════════════════════════════════════════════ */}
        {activeTab === 'skillopt' && (
          <div className="animate-in fade-in duration-300">
            <SkillOptTab />
          </div>
        )}

      </div>
    </div>
  );
}
