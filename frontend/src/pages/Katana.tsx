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
} from "lucide-react";
import axios from 'axios';
import { cn } from '../lib/utils';

type TabType = 'providers' | 'tools' | 'routing' | 'telegram';
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
  ollama:     'http://localhost:11434',
  lmstudio:   'http://localhost:1234/v1',
  local:      'http://localhost:1234/v1',
  custom:     '',
};

const LOCAL_PROVIDERS = ['ollama', 'lmstudio', 'local'];
const isLocalProvider = (type: string) => LOCAL_PROVIDERS.includes(type);

// ── Ollama curated model catalog ─────────────────────────────────
type OllamaCategory = 'general' | 'code' | 'vision' | 'embedding';
interface OllamaModel {
  id: string; name: string; tag: string; size: string;
  category: OllamaCategory; desc: string;
}
const OLLAMA_CATALOG: OllamaModel[] = [
  // General
  { id: 'llama3.2:1b',          name: 'Llama 3.2',       tag: '1B',    size: '1.3 GB', category: 'general',   desc: 'Ultra-fast, great for edge devices' },
  { id: 'llama3.2:3b',          name: 'Llama 3.2',       tag: '3B',    size: '2.0 GB', category: 'general',   desc: 'Compact, excellent reasoning' },
  { id: 'llama3.1:8b',          name: 'Llama 3.1',       tag: '8B',    size: '4.7 GB', category: 'general',   desc: 'Best-in-class 8B open model' },
  { id: 'gemma3:1b',            name: 'Gemma 3',         tag: '1B',    size: '815 MB', category: 'general',   desc: "Google's smallest multimodal" },
  { id: 'gemma3:4b',            name: 'Gemma 3',         tag: '4B',    size: '3.3 GB', category: 'general',   desc: "Google's efficient 4B model" },
  { id: 'gemma3:12b',           name: 'Gemma 3',         tag: '12B',   size: '8.1 GB', category: 'general',   desc: 'High quality, multilingual' },
  { id: 'phi4-mini',            name: 'Phi-4 Mini',      tag: '3.8B',  size: '2.5 GB', category: 'general',   desc: "Microsoft's compact Phi-4" },
  { id: 'phi4',                 name: 'Phi-4',           tag: '14B',   size: '9.1 GB', category: 'general',   desc: "Microsoft's flagship Phi" },
  { id: 'mistral',              name: 'Mistral',         tag: '7B',    size: '4.1 GB', category: 'general',   desc: 'Classic Mistral 7B instruct' },
  { id: 'qwen2.5:7b',           name: 'Qwen 2.5',        tag: '7B',    size: '4.7 GB', category: 'general',   desc: 'Alibaba multilingual model' },
  { id: 'qwen2.5:14b',          name: 'Qwen 2.5',        tag: '14B',   size: '9.0 GB', category: 'general',   desc: 'Strong multilingual reasoning' },
  { id: 'deepseek-r1:7b',       name: 'DeepSeek R1',     tag: '7B',    size: '4.7 GB', category: 'general',   desc: 'Reasoning-first distilled model' },
  { id: 'deepseek-r1:14b',      name: 'DeepSeek R1',     tag: '14B',   size: '9.0 GB', category: 'general',   desc: 'Powerful open-source reasoner' },
  // Code
  { id: 'codellama:7b',         name: 'CodeLlama',       tag: '7B',    size: '3.8 GB', category: 'code',      desc: 'Meta code generation model' },
  { id: 'codellama:13b',        name: 'CodeLlama',       tag: '13B',   size: '7.4 GB', category: 'code',      desc: 'Larger CodeLlama for complex tasks' },
  { id: 'qwen2.5-coder:7b',     name: 'Qwen Coder',      tag: '7B',    size: '4.7 GB', category: 'code',      desc: 'Best open-source code specialist' },
  { id: 'deepseek-coder:6.7b',  name: 'DeepSeek Coder',  tag: '6.7B',  size: '3.8 GB', category: 'code',      desc: 'Code generation and completion' },
  { id: 'starcoder2:7b',        name: 'StarCoder 2',     tag: '7B',    size: '4.0 GB', category: 'code',      desc: 'Trained on 600+ programming languages' },
  // Vision
  { id: 'llava:7b',             name: 'LLaVA',           tag: '7B',    size: '4.5 GB', category: 'vision',    desc: 'Image understanding + chat' },
  { id: 'llava:13b',            name: 'LLaVA',           tag: '13B',   size: '8.0 GB', category: 'vision',    desc: 'Larger, more capable vision model' },
  { id: 'llava-phi3',           name: 'LLaVA Phi-3',     tag: '3.8B',  size: '2.9 GB', category: 'vision',    desc: 'Compact vision model' },
  { id: 'minicpm-v',            name: 'MiniCPM-V',       tag: '8B',    size: '5.5 GB', category: 'vision',    desc: 'Strong OCR and doc understanding' },
  // Embeddings
  { id: 'nomic-embed-text',     name: 'Nomic Embed',     tag: 'text',  size: '274 MB', category: 'embedding', desc: 'High quality text embeddings' },
  { id: 'mxbai-embed-large',    name: 'MXBai Embed',     tag: 'large', size: '670 MB', category: 'embedding', desc: 'SOTA for retrieval tasks' },
  { id: 'all-minilm',           name: 'All-MiniLM',      tag: 'L6-v2', size: '45 MB',  category: 'embedding', desc: 'Ultra-lightweight sentence embedder' },
];

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
  const [activeTab, setActiveTab] = useState<TabType>('providers');

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
  const [tgShowToken, setTgShowToken]   = useState(false);
  const [loading, setLoading]     = useState(true);
  const [saving, setSaving]       = useState(false);

  const [providers, setProviders]   = useState<any[]>([]);
  const [tools, setTools]           = useState<any[]>([]);
  const [localModels, setLocalModels] = useState<string[]>([]);
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  // ── New Provider form state ──────────────────────────────────
  const [newProvider, setNewProvider] = useState({
    name: '',
    provider_type: 'openai',
    auth_type: 'api_key',
    api_key: '',
    base_url: PROVIDER_BASE_URLS['openai'],
    is_active: true
  });
  const [baseUrlOverride, setBaseUrlOverride] = useState(false);
  const [localModelPath, setLocalModelPath]   = useState('');
  const [scanningModels, setScanningModels]   = useState(false);

  // ── Pull-model state ─────────────────────────────────────────
  const [showPullPanel, setShowPullPanel]         = useState(false);
  const [pullCatalogFilter, setPullCatalogFilter] = useState<'all' | OllamaCategory>('all');
  const [pullingModel, setPullingModel]           = useState<string | null>(null);
  const [pullStatus, setPullStatus]               = useState<{ status: string; percent: number } | null>(null);
  const [customPullTag, setCustomPullTag]         = useState('');

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

  // ── Routing profile state ────────────────────────────────────
  const [routingProfiles, setRoutingProfiles]   = useState<any[]>([]);
  const [showCreateProfile, setShowCreateProfile] = useState(false);
  const [profileSaving, setProfileSaving]       = useState(false);
  const [expandedProfileId, setExpandedProfileId] = useState<string | null>(null);
  const [showAddRule, setShowAddRule]           = useState(false);
  const [newProfile, setNewProfile]             = useState({ name: '', description: '', is_default: false });
  const [newRule, setNewRule]                   = useState({
    task_type: '*',
    primary_model_id: '',
    latency_bias: '' as string,
    cost_bias: '' as string,
  });

  useEffect(() => { fetchData(); }, []);

  useEffect(() => {
    if (isLocalProvider(newProvider.provider_type)) {
      fetchLocalModels(newProvider.provider_type);
      // Set a sensible default path when switching to a local provider
      if (!localModelPath) {
        if (newProvider.provider_type === 'ollama') {
          // Windows default; user can override
          setLocalModelPath('%USERPROFILE%\\.ollama\\models');
        } else {
          setLocalModelPath('');
        }
      }
    } else {
      setLocalModels([]);
      setLocalModelPath('');
    }
  }, [newProvider.provider_type]);

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

  // \u2500\u2500 Telegram handlers \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500
  const fetchTgStatus = async () => {
    try {
      const res = await axios.get('/api/v1/channels/telegram/status');
      const d = res.data.data;
      setTgStatus(d);
      if (d?.mode) setTgMode(d.mode);
      if (d?.allowed_chat_ids?.length) setTgChatIds(d.allowed_chat_ids.join(', '));
      if (d?.webhook_url) setTgWebhook(d.webhook_url || '');
    } catch { /* ignore */ }
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
        setStatusMessage({ type: 'error', text: d.error || 'Connection failed.' });
      } else {
        setStatusMessage({ type: 'success', text: `Connected as @${d.bot_username}` });
        setTgToken('');
      }
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to connect Telegram bot.' });
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
    } catch {
      setTgTestResult({ ok: false, error: 'Request failed.' });
    } finally {
      setTgTesting(false);
    }
  };

  const handleTgDisconnect = async () => {
    if (!confirm('Disconnect Telegram bot? The stored token will be removed.')) return;
    try {
      await axios.delete('/api/v1/channels/telegram/disconnect');
      setTgStatus(null);
      setTgChatIds('');
      setTgWebhook('');
      setTgTestResult(null);
      setStatusMessage({ type: 'success', text: 'Telegram bot disconnected.' });
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to disconnect.' });
    } finally {
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  const fetchLocalModels = async (providerType: string) => {
    try {
      const baseUrl = providerType === 'ollama'
        ? (newProvider.base_url || 'http://localhost:11434')
        : (newProvider.base_url || 'http://localhost:1234');

      if (providerType === 'ollama') {
        const res = await axios.get(`${baseUrl}/api/tags`);
        setLocalModels((res.data?.models || []).map((m: any) => m.name || m.model));
      } else {
        const res = await axios.get(`${baseUrl}/v1/models`);
        setLocalModels((res.data?.data || []).map((m: any) => m.id));
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
    const baseUrl = newProvider.base_url || 'http://localhost:11434';
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
        config:        newProvider.api_key ? { api_key: newProvider.api_key } : {},
      };
      await axios.post('/api/v1/model-providers', payload);
      setStatusMessage({ type: 'success', text: 'Model provider added successfully.' });
      setNewProvider({ name: '', provider_type: 'openai', auth_type: 'api_key', api_key: '', base_url: PROVIDER_BASE_URLS['openai'], is_active: true });
      setBaseUrlOverride(false);
      fetchData();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      const msg = typeof detail === 'string' ? detail
        : Array.isArray(detail) ? detail.map((d: any) => `${d.loc?.slice(-1)[0]}: ${d.msg}`).join(', ')
        : 'Failed to add provider.';
      setStatusMessage({ type: 'error', text: msg });
    } finally {
      setSaving(false);
      setTimeout(() => setStatusMessage(null), 5000);
    }
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

  const handleAddRule = async (profileId: string, existingRules: any[]) => {
    if (!newRule.primary_model_id) return;
    const rule = {
      task_type: newRule.task_type,
      primary_model_id: newRule.primary_model_id,
      fallback_model_ids: [],
      latency_bias: newRule.latency_bias || null,
      cost_bias: newRule.cost_bias || null,
    };
    try {
      await axios.patch(`/api/v1/model-routing-profiles/${profileId}`, {
        rules: [...existingRules, rule],
      });
      setStatusMessage({ type: 'success', text: 'Routing rule added.' });
      setShowAddRule(false);
      setNewRule({ task_type: '*', primary_model_id: '', latency_bias: '', cost_bias: '' });
      fetchData();
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to add rule.' });
    } finally {
      setTimeout(() => setStatusMessage(null), 3000);
    }
  };

  const handleDeleteRule = async (profileId: string, existingRules: any[], ruleIdx: number) => {
    const updated = existingRules.filter((_, i) => i !== ruleIdx);
    try {
      await axios.patch(`/api/v1/model-routing-profiles/${profileId}`, { rules: updated });
      setStatusMessage({ type: 'success', text: 'Rule removed.' });
      fetchData();
    } catch {
      setStatusMessage({ type: 'error', text: 'Failed to remove rule.' });
    } finally {
      setTimeout(() => setStatusMessage(null), 3000);
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
            The Katana <span className="text-[10px] font-normal text-shogun-subdued bg-shogun-card px-2 py-0.5 rounded border border-shogun-border tracking-[0.2em] uppercase">Orchestration</span>
          </h2>
          <p className="text-shogun-subdued text-sm mt-1">Manage the cutting-edge models and tools that empower your agents.</p>
        </div>
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
      <div className="flex border-b border-shogun-border">
        {(['providers', 'tools', 'routing', 'telegram'] as TabType[]).map((tab) => (
          <button
            key={tab}
            onClick={() => {
              setActiveTab(tab);
              if (tab === 'telegram' && !tgStatus) fetchTgStatus();
            }}
            className={cn(
              "px-6 py-3 text-sm font-bold uppercase tracking-widest transition-all relative",
              activeTab === tab ? "text-shogun-blue" : "text-shogun-subdued hover:text-shogun-text"
            )}
          >
            {tab === 'providers' && 'Model Providers'}
            {tab === 'tools'     && 'Toolbox & APIs'}
            {tab === 'routing'   && 'Logic Routing'}
            {tab === 'telegram'  && (
              <span className="flex items-center gap-1.5">
                <MessageCircle className="w-3.5 h-3.5" />
                Telegram
                {tgStatus?.connected && (
                  <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
                )}
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
        {activeTab === 'providers' && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Add Provider form */}
            <div className="lg:col-span-1">
              <div className="shogun-card space-y-6 sticky top-6">
                <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                  <Plus className="w-5 h-5 text-shogun-blue" /> Add Provider
                </h3>
                <form onSubmit={handleCreateProvider} className="space-y-4">
                  {/* Provider selector */}
                  <div className="space-y-1.5">
                    <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Provider</label>
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
                        setBaseUrlOverride(false);
                      }}
                      className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                    >
                      <optgroup label="Cloud Providers">
                        <option value="openai">OpenAI</option>
                        <option value="google">Google (Gemini)</option>
                        <option value="anthropic">Anthropic</option>
                        <option value="openrouter">OpenRouter</option>
                      </optgroup>
                      <optgroup label="Local Providers">
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
                      {isLocal ? 'Available Models' : 'Display Name'}
                    </label>
                    {isLocal && localModels.length > 0 ? (
                      <select
                        required
                        value={newProvider.name}
                        onChange={(e) => setNewProvider({...newProvider, name: e.target.value})}
                        className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                      >
                        <option value="" disabled>Select a pulled model...</option>
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
                          <RefreshCw className="w-2.5 h-2.5" /> Scan for local models
                        </button>
                        <span className="text-[9px] text-shogun-subdued">• Ensure {newProvider.provider_type === 'ollama' ? 'Ollama' : 'LM Studio'} is running</span>
                      </div>
                    )}
                  </div>

                  {/* Auth Configuration (cloud only) */}
                  {!isLocal && (
                    <>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Auth Type</label>
                        <select
                          value={newProvider.auth_type}
                          onChange={(e) => setNewProvider({...newProvider, auth_type: e.target.value})}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none"
                        >
                          <option value="api_key">API Key</option>
                          <option value="oauth">OAuth</option>
                        </select>
                      </div>
                      <div className="space-y-1.5 mt-3">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">
                          {newProvider.auth_type === 'oauth' ? 'OAuth Token' : 'API Key'}
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
                        Base URL {isLocal ? '' : '(Auto)'}
                      </label>
                      <button
                        type="button"
                        onClick={() => setBaseUrlOverride(v => !v)}
                        className={cn(
                          "text-[9px] font-bold uppercase tracking-widest transition-colors",
                          baseUrlOverride ? "text-shogun-gold" : "text-shogun-blue hover:text-shogun-gold"
                        )}
                      >
                        {baseUrlOverride ? '↩ Reset' : '✎ Override'}
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
                            Default
                          </span>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Model Location — local providers only */}
                  {isLocal && (
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-1.5">
                        <Folder className="w-3 h-3" /> Model Location
                        <span className="text-shogun-subdued/50 normal-case font-normal tracking-normal text-[9px]">(filesystem path)</span>
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

                  {/* Pull a Model — Ollama only */}
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
                            — download directly to Ollama
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

                          {/* Category filter */}
                          <div className="flex gap-1 flex-wrap">
                            {(['all', 'general', 'code', 'vision', 'embedding'] as const).map(f => (
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

                          {/* Model grid */}
                          <div className="grid grid-cols-1 gap-2 max-h-64 overflow-y-auto pr-1 scrollbar-thin">
                            {OLLAMA_CATALOG
                              .filter(m => pullCatalogFilter === 'all' || m.category === pullCatalogFilter)
                              .map(m => {
                                const isThis = pullingModel === m.id;
                                const alreadyHave = localModels.includes(m.id) || localModels.includes(m.name);
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
                                      <div className="flex items-center gap-2">
                                        <span className="text-[10px] font-bold text-shogun-text truncate">{m.name}</span>
                                        <span className="text-[8px] px-1.5 py-0.5 rounded bg-shogun-card border border-shogun-border text-shogun-subdued font-bold shrink-0">{m.tag}</span>
                                        {alreadyHave && <span className="text-[8px] text-green-400 font-bold shrink-0">✓ local</span>}
                                      </div>
                                      <div className="flex items-center gap-2 mt-0.5">
                                        <span className="text-[8px] font-mono text-cyan-400/60">{m.size}</span>
                                        <span className="text-[8px] text-shogun-subdued/70 truncate">{m.desc}</span>
                                      </div>
                                    </div>
                                    <button
                                      type="button"
                                      disabled={!!pullingModel}
                                      onClick={() => handlePullModel(m.id)}
                                      className={cn(
                                        "ml-3 shrink-0 flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-[9px] font-bold uppercase transition-all border",
                                        isThis
                                          ? "border-cyan-500/40 text-cyan-400 bg-cyan-500/10 animate-pulse"
                                          : alreadyHave
                                            ? "border-green-500/20 text-green-400 bg-green-500/5 hover:bg-green-500/10"
                                            : "border-shogun-border text-shogun-subdued hover:border-cyan-500/50 hover:text-cyan-400 hover:bg-cyan-500/5 disabled:opacity-30 disabled:cursor-not-allowed"
                                      )}
                                    >
                                      {isThis
                                        ? <><RefreshCw className="w-2.5 h-2.5 animate-spin" /> Pulling</>
                                        : alreadyHave
                                          ? <><RefreshCw className="w-2.5 h-2.5" /> Re-pull</>
                                          : <><Download className="w-2.5 h-2.5" /> Pull</>}
                                    </button>
                                  </div>
                                );
                              })}
                          </div>

                          {/* Custom model tag */}
                          <div className="pt-2 border-t border-shogun-border/50 space-y-1.5">
                            <label className="text-[9px] font-bold text-shogun-subdued uppercase tracking-widest">Custom Model Tag</label>
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
                                <Download className="w-3 h-3" /> Pull
                              </button>
                            </div>
                            <p className="text-[9px] text-shogun-subdued/60">Any valid Ollama model tag from <span className="text-cyan-400/70 font-mono">ollama.com/library</span></p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  <button
                    type="submit"
                    disabled={saving}
                    className="w-full py-3 bg-shogun-blue hover:bg-shogun-blue/90 text-white font-bold rounded-lg shadow-shogun transition-all flex items-center justify-center gap-2"
                  >
                    {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                    INITIATE PROVIDER
                  </button>
                </form>
              </div>
            </div>

            {/* Active Providers grid */}
            <div className="lg:col-span-2 space-y-6">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <Cpu className="w-5 h-5 text-shogun-blue" /> Active Providers
              </h3>

              {loading ? (
                <div className="p-12 text-center shogun-card opacity-50">
                  <RefreshCw className="w-8 h-8 animate-spin mx-auto text-shogun-blue mb-4" />
                  <p className="text-xs uppercase tracking-widest font-bold">Querying Model Grid...</p>
                </div>
              ) : providers.length === 0 ? (
                <div className="p-12 text-center shogun-card border-dashed">
                  <p className="text-shogun-subdued italic">No model providers configured. Agents will be offline.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-4">
                  {providers.map((p) => {
                    const color   = getProviderColor(p.provider_type);
                    const docLink = PROVIDER_DOCS[p.provider_type];
                    const isActive = p.status === 'connected';
                    return (
                      <div key={p.id} className="shogun-card group hover:border-shogun-blue/50 transition-all">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center font-bold text-xl", color.bg, color.text)}>
                              {p.provider_type[0].toUpperCase()}
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <h4 className="font-bold text-shogun-text">{p.name}</h4>
                                {isActive
                                  ? <span className="text-[8px] bg-green-500/10 text-green-500 px-1.5 py-0.5 rounded border border-green-500/20 font-bold uppercase">Active</span>
                                  : <span className="text-[8px] bg-shogun-subdued/10 text-shogun-subdued px-1.5 py-0.5 rounded border border-shogun-border font-bold uppercase">{p.status ?? 'Not configured'}</span>
                                }
                              </div>
                              <div className="flex items-center gap-2 mt-1">
                                <span className="text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded bg-[#050508] border border-shogun-border text-shogun-subdued">
                                  {getProviderDisplayType(p.provider_type)}
                                </span>
                                <span className="text-xs text-shogun-subdued">{p.base_url || 'Default Endpoint'}</span>
                              </div>
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
                              onClick={() => handleToggleProvider(p.id, p.status)}
                              className="p-2 hover:bg-shogun-card rounded-lg transition-colors text-shogun-subdued hover:text-shogun-text"
                              title={isActive ? 'Disable' : 'Enable'}
                            >
                              {isActive ? <Zap className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4" />}
                            </button>
                            <button
                              onClick={() => handleDeleteProvider(p.id, p.name)}
                              className="p-2 hover:bg-red-500/10 text-red-500/50 hover:text-red-500 rounded-lg transition-colors"
                              title="Delete Provider"
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
                <Wrench className="w-5 h-5 text-shogun-blue" /> Tool Connectors
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
                {showRegisterTool ? 'Cancel' : 'Register New Tool'}
              </button>
            </div>

            {/* ── Register Panel ────────────────────────────────── */}
            {showRegisterTool && (
              <div className="shogun-card border-shogun-blue/30 animate-in slide-in-from-top-3 duration-300">
                <div className="flex items-center justify-between mb-5">
                  <h4 className="font-bold text-shogun-text flex items-center gap-2">
                    <Puzzle className="w-4 h-4 text-shogun-blue" /> Register Tool Connector
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
                        {m === 'quick' ? '⚡ Quick Pick' : '✏️ Manual'}
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
                            placeholder="Search APIs... (e.g. stripe, weather, openai)"
                            value={apiSearch}
                            onChange={(e) => setApiSearch(e.target.value)}
                            className="w-full bg-[#050508] border border-shogun-border rounded-lg pl-9 pr-3 py-2.5 text-sm focus:border-shogun-blue outline-none"
                          />
                        </div>
                        <div className="h-64 overflow-y-auto space-y-1 pr-1 scrollbar-thin scrollbar-thumb-shogun-border scrollbar-track-transparent">
                          {filteredApis.length === 0 ? (
                            <p className="text-xs text-shogun-subdued italic text-center py-8">No APIs match your search.</p>
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
                                { label: 'Endpoint', value: selectedApi.base_url },
                                { label: 'Auth',     value: selectedApi.auth_type.replace('_', ' ').toUpperCase() },
                                { label: 'Type',     value: selectedApi.connector_type.toUpperCase() },
                                { label: 'Risk',     value: selectedApi.risk_level.toUpperCase() },
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
                            <p className="text-xs text-shogun-subdued">Select an API from the list to preview it here.</p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* ── MANUAL ENTRY MODE ───────────────────────── */}
                  {registerMode === 'manual' && (
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Tool Name *</label>
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
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Slug *</label>
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
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Base URL</label>
                        <input
                          type="text"
                          placeholder="https://api.example.com/v1"
                          value={newTool.base_url}
                          onChange={(e) => setNewTool({ ...newTool, base_url: e.target.value })}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none font-mono"
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Connector Type</label>
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
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Auth Type</label>
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
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Risk Level</label>
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
                      Register Connector
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowRegisterTool(false)}
                      className="px-4 py-2.5 text-sm font-bold text-shogun-subdued hover:text-shogun-text transition-colors"
                    >
                      Cancel
                    </button>
                    {registerMode === 'quick' && !selectedApi && (
                      <p className="text-[10px] text-shogun-subdued ml-auto">← Select an API first</p>
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
                  <p className="text-xs uppercase tracking-widest font-bold">Loading Connectors...</p>
                </div>
              ) : tools.length === 0 ? (
                <div className="col-span-3 p-12 text-center shogun-card border-dashed">
                  <Wrench className="w-8 h-8 text-shogun-subdued opacity-30 mx-auto mb-3" />
                  <p className="text-shogun-subdued italic text-sm">No tool connectors found. Agents are currently primitive.</p>
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
                  <button
                    onClick={() => handleDeleteTool(tool.id, tool.name)}
                    className="absolute top-3 right-3 p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-red-500/10 text-red-500/50 hover:text-red-500 transition-all"
                    title="Remove connector"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>

                  <div className="flex items-start gap-3 mb-4">
                    <div className="w-10 h-10 rounded-lg bg-[#050508] border border-shogun-border flex items-center justify-center text-shogun-subdued group-hover:text-shogun-blue transition-colors shrink-0">
                      <Wrench className="w-5 h-5" />
                    </div>
                    <div className="min-w-0">
                      <h4 className="font-bold text-shogun-text truncate">{tool.name}</h4>
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
            ROUTING TAB
        ════════════════════════════════════════════════════════ */}
        {activeTab === 'routing' && (
          <div className="space-y-6">

            {/* ── Header ──────────────────────────────────────── */}
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                <SlidersHorizontal className="w-5 h-5 text-shogun-blue" /> Routing Profiles
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
                {showCreateProfile ? 'Cancel' : 'New Profile'}
              </button>
            </div>

            {/* ── Create Profile Panel ──────────────────────── */}
            {showCreateProfile && (
              <div className="shogun-card border-shogun-blue/30 animate-in slide-in-from-top-3 duration-300">
                <h4 className="font-bold text-shogun-text flex items-center gap-2 mb-4">
                  <GitBranch className="w-4 h-4 text-shogun-blue" /> New Routing Profile
                </h4>
                <form onSubmit={handleCreateProfile}>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Profile Name *</label>
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
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Description</label>
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
                      Set as default profile
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
                <p className="text-xs uppercase tracking-widest font-bold">Loading Profiles...</p>
              </div>
            ) : routingProfiles.length === 0 ? (
              <div className="shogun-card text-center py-20 space-y-4 border-dashed">
                <div className="w-16 h-16 bg-shogun-blue/10 rounded-full flex items-center justify-center mx-auto">
                  <ArrowRightLeft className="w-8 h-8 text-shogun-blue" />
                </div>
                <div>
                  <h4 className="font-bold text-shogun-text">No Routing Profiles</h4>
                  <p className="text-sm text-shogun-subdued mt-1 max-w-sm mx-auto">
                    Create a profile to define how tasks are routed to specific model providers.
                  </p>
                </div>
                <button
                  onClick={() => setShowCreateProfile(true)}
                  className="text-[10px] font-bold text-shogun-blue hover:text-shogun-gold uppercase tracking-widest transition-colors"
                >
                  + Create your first profile
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
                                  Default
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-shogun-subdued mt-0.5">
                              {profile.description || 'No description.'}
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
                            {rules.length} {rules.length === 1 ? 'rule' : 'rules'}
                            {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          </button>

                          {/* Set default */}
                          {!profile.is_default && (
                            <button
                              onClick={() => handleSetDefault(profile.id)}
                              className="p-2 hover:bg-shogun-gold/10 text-shogun-subdued hover:text-shogun-gold rounded-lg transition-colors"
                              title="Set as default"
                            >
                              <StarOff className="w-4 h-4" />
                            </button>
                          )}

                          {/* Delete profile */}
                          <button
                            onClick={() => handleDeleteProfile(profile.id, profile.name)}
                            className="p-2 hover:bg-red-500/10 text-red-500/40 hover:text-red-500 rounded-lg transition-colors"
                            title="Delete profile"
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
                            <p className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Routing Rules</p>
                            {!showAddRule && (
                              <button
                                onClick={() => setShowAddRule(true)}
                                className="flex items-center gap-1 text-[10px] font-bold text-shogun-blue hover:text-shogun-gold uppercase tracking-widest transition-colors"
                              >
                                <Plus className="w-3 h-3" /> Add Rule
                              </button>
                            )}
                          </div>

                          {/* Existing rules */}
                          {rules.length === 0 && !showAddRule ? (
                            <div className="text-center py-6 bg-[#050508] rounded-xl border border-dashed border-shogun-border">
                              <p className="text-xs text-shogun-subdued italic">No rules yet — all requests fall through to the default model.</p>
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
                                        <p className="text-[9px] text-shogun-subdued uppercase tracking-widest font-bold">Task Type</p>
                                        <p className="text-xs font-bold text-shogun-text">
                                          {rule.task_type === '*' ? 'All Tasks' : rule.task_type}
                                        </p>
                                      </div>
                                      <div>
                                        <p className="text-[9px] text-shogun-subdued uppercase tracking-widest font-bold">Primary Model</p>
                                        <p className="text-xs font-bold text-shogun-text truncate">
                                          {primaryProvider?.name || (
                                            <span className="text-red-400/70 text-[10px]">Unlinked</span>
                                          )}
                                        </p>
                                      </div>
                                      <div>
                                        <p className="text-[9px] text-shogun-subdued uppercase tracking-widest font-bold">Latency</p>
                                        <p className="text-xs text-shogun-text">{rule.latency_bias || <span className="text-shogun-subdued">—</span>}</p>
                                      </div>
                                      <div>
                                        <p className="text-[9px] text-shogun-subdued uppercase tracking-widest font-bold">Cost</p>
                                        <p className="text-xs text-shogun-text">{rule.cost_bias || <span className="text-shogun-subdued">—</span>}</p>
                                      </div>
                                    </div>
                                    <button
                                      onClick={() => handleDeleteRule(profile.id, rules, idx)}
                                      className="p-1.5 opacity-0 group-hover:opacity-100 rounded-lg hover:bg-red-500/10 text-red-500/50 hover:text-red-500 transition-all shrink-0"
                                      title="Remove rule"
                                    >
                                      <Trash2 className="w-3.5 h-3.5" />
                                    </button>
                                  </div>
                                );
                              })}
                            </div>
                          )}

                          {/* Add Rule form */}
                          {showAddRule && (
                            <div className="bg-shogun-blue/5 border border-shogun-blue/20 rounded-xl p-4 space-y-4 animate-in slide-in-from-top-2 duration-200">
                              <p className="text-[10px] font-bold text-shogun-blue uppercase tracking-widest flex items-center gap-1.5">
                                <Plus className="w-3 h-3" /> New Routing Rule
                              </p>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                {/* Task Type */}
                                <div className="space-y-1.5">
                                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Task Type</label>
                                  <select
                                    value={newRule.task_type}
                                    onChange={e => setNewRule({ ...newRule, task_type: e.target.value })}
                                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue outline-none"
                                  >
                                    <option value="*">* All Tasks (wildcard)</option>
                                    <option value="research">Research & Information Gathering</option>
                                    <option value="code">Code & Engineering</option>
                                    <option value="analysis">Analysis & Reasoning</option>
                                    <option value="creative">Creative Generation</option>
                                    <option value="summarize">Summarization</option>
                                    <option value="planning">Planning & Strategy</option>
                                    <option value="qa">QA & Verification</option>
                                    <option value="chat">Chat & Conversation</option>
                                    <option value="extraction">Data Extraction</option>
                                    <option value="translation">Translation</option>
                                    <option value="vision">Vision & Multimodal</option>
                                  </select>
                                </div>

                                {/* Primary Model */}
                                <div className="space-y-1.5">
                                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Primary Model Provider *</label>
                                  <select
                                    value={newRule.primary_model_id}
                                    onChange={e => setNewRule({ ...newRule, primary_model_id: e.target.value })}
                                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue outline-none"
                                  >
                                    <option value="">Select a provider...</option>
                                    {providers.map(p => (
                                      <option key={p.id} value={p.id}>
                                        {p.name} — {p.provider_type}
                                      </option>
                                    ))}
                                    {providers.length === 0 && (
                                      <option disabled>No providers configured yet</option>
                                    )}
                                  </select>
                                  {providers.length === 0 && (
                                    <p className="text-[9px] text-yellow-400">⚠ Add a Model Provider first</p>
                                  )}
                                </div>

                                {/* Latency Bias */}
                                <div className="space-y-1.5">
                                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Latency Bias</label>
                                  <select
                                    value={newRule.latency_bias}
                                    onChange={e => setNewRule({ ...newRule, latency_bias: e.target.value })}
                                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue outline-none"
                                  >
                                    <option value="">None (unbiased)</option>
                                    <option value="low">Low — Prioritise speed</option>
                                    <option value="medium">Medium — Balanced</option>
                                    <option value="high">High — Tolerate latency for quality</option>
                                  </select>
                                </div>

                                {/* Cost Bias */}
                                <div className="space-y-1.5">
                                  <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Cost Bias</label>
                                  <select
                                    value={newRule.cost_bias}
                                    onChange={e => setNewRule({ ...newRule, cost_bias: e.target.value })}
                                    className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue outline-none"
                                  >
                                    <option value="">None (unbiased)</option>
                                    <option value="budget">Budget — Prefer cheapest model</option>
                                    <option value="standard">Standard — Balance cost/quality</option>
                                    <option value="premium">Premium — Best model regardless of cost</option>
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
                                  <Save className="w-3.5 h-3.5" /> Save Rule
                                </button>
                                <button
                                  type="button"
                                  onClick={() => { setShowAddRule(false); setNewRule({ task_type: '*', primary_model_id: '', latency_bias: '', cost_bias: '' }); }}
                                  className="px-4 py-2 text-sm text-shogun-subdued hover:text-shogun-text transition-colors font-bold"
                                >
                                  Cancel
                                </button>
                                {!newRule.primary_model_id && (
                                  <span className="text-[10px] text-shogun-subdued ml-auto">← Select a provider to continue</span>
                                )}
                              </div>
                            </div>
                          )}

                          {/* Routing logic legend */}
                          <div className="flex items-start gap-2 mt-2 px-1">
                            <Shield className="w-3 h-3 text-shogun-subdued mt-0.5 shrink-0" />
                            <p className="text-[10px] text-shogun-subdued leading-relaxed">
                              Rules are evaluated top-to-bottom. The first matching <code className="text-shogun-blue font-mono">task_type</code> wins.
                              Use <code className="text-shogun-blue font-mono">*</code> as the last rule to catch all unmatched tasks.
                            </p>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ══ TELEGRAM TAB ══════════════════════════════════════════ */}
        {activeTab === 'telegram' && (
          <div className="space-y-6 animate-in fade-in duration-300">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold flex items-center gap-2 text-shogun-text">
                  <MessageCircle className="w-5 h-5 text-shogun-blue" /> Telegram Channel
                </h3>
                <p className="text-xs text-shogun-subdued mt-1">Connect a Telegram bot to chat with Shogun directly from your phone.</p>
              </div>
              {tgStatus?.connected && (
                <div className="flex items-center gap-2 px-3 py-1.5 bg-green-400/10 border border-green-400/30 rounded-lg">
                  <Wifi className="w-3.5 h-3.5 text-green-400" />
                  <span className="text-xs font-bold text-green-400">Connected</span>
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
                          Mode: <span className="font-bold uppercase text-green-400">{tgStatus.mode}</span>
                          {tgStatus.last_connected_at && <> · {new Date(tgStatus.last_connected_at).toLocaleDateString()}</>}
                        </p>
                      </div>
                    </div>
                    <button onClick={handleTgDisconnect}
                      className="flex items-center gap-1.5 px-3 py-1.5 border border-red-400/30 text-red-400/70 hover:text-red-400 hover:border-red-400/50 rounded-lg text-xs font-bold transition-all">
                      <WifiOff className="w-3.5 h-3.5" /> Disconnect
                    </button>
                  </div>
                )}

                <div className="shogun-card space-y-5">
                  <h4 className="text-sm font-bold text-shogun-text">
                    {tgStatus?.connected ? 'Update Configuration' : 'Connect a Bot'}
                  </h4>
                  <form onSubmit={handleTgConnect} className="space-y-4">
                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-1.5">
                        <ShieldCheck className="w-3 h-3 text-shogun-gold" /> Bot Token *
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
                        Get a token from <a href="https://t.me/BotFather" target="_blank" rel="noreferrer" className="text-shogun-blue hover:underline">@BotFather</a>.
                      </p>
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Update Mode</label>
                      <div className="flex gap-2">
                        {(['polling', 'webhook'] as const).map(m => (
                          <button key={m} type="button" onClick={() => setTgMode(m)}
                            className={cn('flex-1 py-2 rounded-lg border text-xs font-bold uppercase tracking-widest transition-all',
                              tgMode === m ? 'bg-shogun-blue text-white border-shogun-blue' : 'border-shogun-border text-shogun-subdued hover:border-shogun-blue/40')}>
                            {m === 'polling' ? '🔄 Polling' : '🌐 Webhook'}
                          </button>
                        ))}
                      </div>
                      <p className="text-[9px] text-shogun-subdued/60">
                        {tgMode === 'polling' ? 'Shogun polls Telegram. Simple, no public URL needed.' : 'Telegram pushes to your server. Requires a public HTTPS URL.'}
                      </p>
                    </div>

                    {tgMode === 'webhook' && (
                      <div className="space-y-1.5">
                        <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest">Webhook URL *</label>
                        <input type="url" required placeholder="https://yourdomain.com/telegram/webhook"
                          value={tgWebhook} onChange={e => setTgWebhook(e.target.value)}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none font-mono" />
                      </div>
                    )}

                    <div className="space-y-1.5">
                      <label className="text-[10px] font-bold text-shogun-subdued uppercase tracking-widest flex items-center gap-1.5">
                        <Shield className="w-3 h-3 text-shogun-gold" /> Allowed Chat IDs
                        <span className="font-normal normal-case tracking-normal text-shogun-subdued/50">(optional whitelist)</span>
                      </label>
                      <input type="text" placeholder="e.g. 123456789, -987654321"
                        value={tgChatIds} onChange={e => setTgChatIds(e.target.value)}
                        className="w-full bg-[#050508] border border-shogun-border rounded-lg p-3 text-sm focus:border-shogun-blue outline-none font-mono" />
                      <p className="text-[9px] text-shogun-subdued/60">Comma-separated IDs. Leave empty to allow all. Negative IDs = groups.</p>
                    </div>

                    <button type="submit" disabled={tgSaving || !tgToken.trim()}
                      className="w-full flex items-center justify-center gap-2 py-3 bg-shogun-blue hover:bg-shogun-blue/90 disabled:opacity-40 text-white font-bold rounded-lg text-sm transition-all">
                      {tgSaving
                        ? <><RefreshCw className="w-4 h-4 animate-spin" /> Connecting…</>
                        : <><MessageCircle className="w-4 h-4" /> {tgStatus?.connected ? 'Update Connection' : 'Connect Bot'}</>}
                    </button>
                  </form>
                </div>
              </div>

              {/* Right: test + guide */}
              <div className="lg:col-span-2 space-y-5">
                <div className="shogun-card space-y-4">
                  <h4 className="text-sm font-bold text-shogun-text flex items-center gap-2">
                    <Send className="w-4 h-4 text-shogun-blue" /> Test Message
                  </h4>
                  {!tgStatus?.connected
                    ? <p className="text-center py-6 text-shogun-subdued text-xs italic">Connect a bot first.</p>
                    : (
                      <div className="space-y-3">
                        <input type="text" placeholder="Your chat ID, e.g. 123456789"
                          value={tgTestChat} onChange={e => setTgTestChat(e.target.value)}
                          className="w-full bg-[#050508] border border-shogun-border rounded-lg p-2.5 text-sm focus:border-shogun-blue outline-none font-mono" />
                        <button onClick={handleTgTest} disabled={tgTesting || !tgTestChat.trim()}
                          className="w-full flex items-center justify-center gap-2 py-2.5 border border-shogun-blue/40 bg-shogun-blue/10 hover:bg-shogun-blue/20 text-shogun-blue disabled:opacity-40 font-bold rounded-lg text-sm transition-all">
                          {tgTesting ? <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Sending…</> : <><Send className="w-3.5 h-3.5" /> Send Test</>}
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
                    <ChevronRight className="w-4 h-4 text-shogun-gold" /> Quick Setup
                  </h4>
                  <ol className="space-y-3">
                    {[
                      { n: '1', t: 'Message @BotFather on Telegram', href: 'https://t.me/BotFather' },
                      { n: '2', t: 'Send /newbot — follow the prompts' },
                      { n: '3', t: 'Copy the bot token BotFather gives you' },
                      { n: '4', t: 'Paste above and click Connect Bot' },
                      { n: '5', t: 'Add your chat ID to the whitelist' },
                    ].map(({ n, t, href }) => (
                      <li key={n} className="flex items-start gap-3">
                        <span className="w-5 h-5 rounded-full bg-shogun-blue/20 border border-shogun-blue/40 text-shogun-blue text-[9px] font-bold flex items-center justify-center shrink-0 mt-0.5">{n}</span>
                        <span className="text-xs text-shogun-subdued leading-relaxed">
                          {t}{href && <> — <a href={href} target="_blank" rel="noreferrer" className="text-shogun-blue hover:underline">{href.split('//')[1]}</a></>}
                        </span>
                      </li>
                    ))}
                  </ol>
                  <div className="pt-2 border-t border-shogun-border">
                    <p className="text-[9px] text-shogun-subdued/60">
                      Find your chat ID via <a href="https://t.me/userinfobot" target="_blank" rel="noreferrer" className="text-shogun-blue hover:underline">@userinfobot</a>.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}
