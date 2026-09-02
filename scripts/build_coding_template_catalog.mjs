import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const catalogPath = path.join(root, 'shogun', 'resources', 'flow_templates.json');

const specs = [
  ['feature-build', 'Full-Stack Feature Build', 'Design and implement a complete feature with explicit contracts, migrations, tests, and rollout checks.'],
  ['bug-fix', 'Root-Cause Bug Fix', 'Reproduce a defect, isolate its root cause, define the smallest safe patch, and verify against regression.'],
  ['refactor', 'Behavior-Preserving Refactor', 'Restructure a subsystem in reversible stages while preserving public behavior and test evidence.'],
  ['test-generation', 'Test Coverage Expansion', 'Map meaningful coverage gaps and add focused unit, integration, and boundary tests.'],
  ['documentation', 'Code-Aligned Documentation', 'Inspect implemented behavior and update API, operator, architecture, and changelog documentation.'],
  ['api-endpoint', 'API Endpoint Delivery', 'Specify and implement a production-ready API endpoint with validation, authorization, errors, and tests.'],
  ['database-migration', 'Safe Database Migration', 'Plan a forward-compatible schema migration with backfill, rollback, and deployment verification.'],
  ['security-hardening', 'Security Hardening Review', 'Threat-model a code path, identify exploitable weaknesses, and define tested hardening changes.'],
  ['performance', 'Performance Optimization', 'Profile a measured bottleneck and design an optimization with benchmarks and regression safeguards.'],
  ['dependency-upgrade', 'Dependency Upgrade', 'Upgrade a dependency while tracing breaking changes, compatibility constraints, and verification.'],
  ['frontend-component', 'Frontend Component Build', 'Build an accessible, responsive UI component with states, tests, and integration boundaries.'],
  ['backend-service', 'Backend Service Build', 'Implement a cohesive backend service with domain rules, persistence, observability, and tests.'],
  ['cli-command', 'CLI Command Delivery', 'Add a safe command-line workflow with parsing, help text, exit codes, and automated tests.'],
  ['auth-flow', 'Authentication Flow', 'Implement an authentication flow with secure session handling, failure paths, and abuse controls.'],
  ['authorization', 'Authorization Policy', 'Implement and verify least-privilege authorization across API, service, and data boundaries.'],
  ['async-worker', 'Async Worker Pipeline', 'Design a reliable background worker with idempotency, retries, timeouts, and dead-letter handling.'],
  ['event-integration', 'Event Integration', 'Add an event producer or consumer with schemas, compatibility, retries, and observability.'],
  ['cache-layer', 'Cache Layer', 'Introduce a cache with explicit consistency, invalidation, fallback, and performance verification.'],
  ['observability', 'Observability Instrumentation', 'Add structured logs, metrics, traces, and actionable diagnostics to a critical path.'],
  ['accessibility', 'Accessibility Remediation', 'Audit and repair keyboard, semantic, focus, contrast, and assistive-technology behavior.'],
  ['internationalization', 'Internationalization Retrofit', 'Externalize UI copy and add locale-safe formatting, fallback behavior, and translation tests.'],
  ['mobile-responsive', 'Responsive UI Retrofit', 'Adapt an existing interface for mobile and intermediate viewports without desktop regressions.'],
  ['data-pipeline', 'Data Pipeline Build', 'Implement a validated, restartable data pipeline with lineage, quality checks, and failure recovery.'],
  ['sdk-client', 'SDK Client Build', 'Create a typed client with stable errors, pagination, retries, examples, and contract tests.'],
  ['legacy-modernization', 'Legacy Module Modernization', 'Characterize legacy behavior and migrate it incrementally behind verified compatibility seams.'],
  ['monorepo-change', 'Cross-Package Monorepo Change', 'Coordinate a change across packages with dependency order, contracts, builds, and release impact.'],
  ['release-readiness', 'Release Readiness', 'Inspect a release candidate for test, migration, security, documentation, and rollback readiness.'],
  ['code-review', 'Deep Code Review', 'Review a change for correctness, security, maintainability, tests, and concrete blocking issues.'],
  ['merge-conflict', 'Merge Conflict Resolution', 'Resolve conflicting intent while preserving behavior from both branches and verifying the result.'],
  ['incident-recovery', 'Production Incident Recovery', 'Diagnose a production code incident, design containment and repair, and capture prevention evidence.'],
  ['complex-game-build', 'Complex Game Build', 'Build a relatively complex playable game with a core loop, state management, progression, AI or simulation systems, polished interaction, persistence, and automated verification.'],
  ['website-build', 'Production Website Build', 'Build a responsive production website with coherent information architecture, accessible components, content integration, performance safeguards, SEO metadata, and deployment verification.'],
  ['business-app-build', 'Business Application Build', 'Build a multi-role business application with domain workflows, validated data entry, persistence, authorization, reporting, auditability, and end-to-end verification.'],
];

const edge = (source_node_id, target_node_id) => ({
  source_node_id, target_node_id, edge_type: 'default', config: {},
});

function makeTemplate([slug, name, description], index) {
  const advanced = index % 3 === 2;
  const nodes = [
    {
      id: 'coding-input', node_type: 'input', label: 'Coding Objective',
      position_x: 0, position_y: 220,
      config: { input_type: 'manual', description, manual_input: '' },
    },
    {
      id: 'coding-plan', node_type: 'coding', label: name,
      position_x: 330, position_y: 220,
      config: {
        action: 'analyze', task_description: description,
        expected_output: 'Repository-aware implementation plan with affected files, risks, tests, and verification.',
        recall_memory: true, memory_limit: advanced ? 8 : 5,
        include_global_memory: advanced, remember_on_success: false, timeout: advanced ? 600 : 300,
      },
    },
    {
      id: 'coding-review', node_type: 'shogun_approval', label: 'Engineering Quality Gate',
      position_x: 660, position_y: 220,
      config: { approval_mode: 'ai_assisted', confidence_threshold: advanced ? 92 : 88 },
    },
    {
      id: 'coding-output', node_type: 'output', label: 'Verified Coding Plan',
      position_x: 990, position_y: 220,
      config: { output_type: 'artifact', format: 'markdown' },
    },
  ];
  return {
    id: `coding-${slug}`, name, description, category: 'Coding', icon: '💻',
    difficulty: advanced ? 'advanced' : index % 3 === 1 ? 'intermediate' : 'beginner',
    trigger_type: 'manual', node_count: nodes.length, nodes,
    edges: [
      edge('coding-input', 'coding-plan'),
      edge('coding-plan', 'coding-review'),
      edge('coding-review', 'coding-output'),
    ],
  };
}

const catalog = JSON.parse(fs.readFileSync(catalogPath, 'utf8'));
catalog.templates = catalog.templates.filter((item) => item.category !== 'Coding');
catalog.templates.push(...specs.map(makeTemplate));
catalog.categories = catalog.categories.filter((item) => item.name !== 'Coding');
catalog.categories.push({ name: 'Coding', count: specs.length, templates: specs.map(([slug]) => `coding-${slug}`) });
catalog.total_templates = catalog.templates.length;
fs.writeFileSync(catalogPath, `${JSON.stringify(catalog, null, 2)}\n`);

console.log(`Built ${specs.length} Coding AgentFlow catalog entries.`);
