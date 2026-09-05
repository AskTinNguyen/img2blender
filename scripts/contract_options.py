"""Optional schema-v2 task intent and scoped evidence contracts.

Absent fields preserve the original reconstruction workflow. No declared scope waives
critical feature gates or permits changing an already pinned contract silently.
"""
from pathlib import Path
import hashlib

TASK_MODES = {'faithful-reconstruction', 'constrained-redesign', 'creative-redesign'}
VALIDATION_SCOPES = {'visual-asset', 'animated-assembly', 'fabrication'}
AUTHORITIES = {'geometry-evidence', 'design-proposal', 'material-inspiration', 'context'}


def file_matches(record):
    path = Path(str(record.get('path', ''))).expanduser()
    try:
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
        return digest.hexdigest() == record.get('sha256')
    except OSError:
        return False


def validate_options(spec):
    errors = []
    mode = spec.get('taskMode', 'faithful-reconstruction')
    if not isinstance(mode, str) or mode not in TASK_MODES:
        errors.append('taskMode is invalid')
    validation = spec.get('validationScope', 'visual-asset')
    if not isinstance(validation, str) or validation not in VALIDATION_SCOPES:
        errors.append('validationScope is invalid')
    intent = spec.get('designIntent', {})
    if not isinstance(intent, dict):
        errors.append('designIntent must be an object')
        intent = {}
    if isinstance(mode, str) and mode in {'constrained-redesign', 'creative-redesign'}:
        for field in ('authorization', 'preservedRequirements', 'allowedChanges'):
            value = intent.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f'designIntent.{field} is required for redesign')
        for ref in (spec.get('references') if isinstance(spec.get('references'), list) else []):
            if isinstance(ref, dict) and (not isinstance(ref.get('authority'), str) or ref['authority'] not in AUTHORITIES):
                errors.append('Redesign references require a valid authority')
    for ref in (spec.get('references') if isinstance(spec.get('references'), list) else []):
        if isinstance(ref, dict) and 'authority' in ref and (not isinstance(ref['authority'], str) or ref['authority'] not in AUTHORITIES):
            errors.append('references.authority is invalid')
    scope = spec.get('refinementScope')
    if scope is not None:
        if not isinstance(scope, dict):
            errors.append('refinementScope must be an object')
        else:
            for field in ('changedComponents', 'affectedInterfaces'):
                value = scope.get(field)
                if not isinstance(value, list) or not value or any(not isinstance(x, str) or not x.strip() for x in value):
                    errors.append(f'refinementScope.{field} must list exact components/interfaces')
            for field in ('baselineCheckpoint', 'baselineEvidence'):
                record = scope.get(field, {})
                if not isinstance(record, dict):
                    errors.append(f'refinementScope.{field} must be a hashed file record')
                    continue
                if not file_matches(record):
                    errors.append(f'refinementScope.{field} must identify an existing hash-matched file')
            if not isinstance(scope.get('rationale'), str) or not scope['rationale'].strip():
                errors.append('refinementScope.rationale is required')
            routes = spec.get('subjectRoutes', [])
            if isinstance(routes, list) and 'architecture-environment' in routes:
                errors.append('Component refinement must select component routes; retain architecture-environment for layout/structure changes')
            contract = spec.get('qualityContract')
            views = contract.get('requiredViews', []) if isinstance(contract, dict) else []
            if not isinstance(views, list) or 'integration-context' not in views:
                errors.append('Component refinement requires integration-context evidence')
    plans = spec.get('inspectionPlan', [])
    if not isinstance(plans, list):
        errors.append('inspectionPlan must be a list')
        return errors
    features = spec.get('featureContract', [])
    ids = {x.get('featureId') for x in (features if isinstance(features, list) else [])
           if isinstance(x, dict) and isinstance(x.get('featureId'), str)}
    seen = set()
    seen_roles = set()
    for plan in plans:
        if not isinstance(plan, dict):
            errors.append('inspectionPlan entries must be objects')
            continue
        feature = plan.get('featureId')
        if not isinstance(feature, str) or feature not in ids or feature in seen:
            errors.append('inspectionPlan.featureId must uniquely name a featureContract entry')
        if isinstance(feature, str): seen.add(feature)
        views = plan.get('views')
        if not isinstance(views, list) or not views:
            errors.append('inspectionPlan.views must be nonempty')
            continue
        for view in views:
            if not isinstance(view, dict):
                errors.append('inspectionPlan.views entries must be objects')
                continue
            if not isinstance(view.get('mode'), str) or view['mode'] not in {'assembled', 'isolated', 'section'}:
                errors.append('Inspection mode must be assembled, isolated, or section')
            if not isinstance(view.get('proves'), str) or view['proves'] not in {'detail', 'installed-fit'}:
                errors.append('Inspection proves must be detail or installed-fit')
            if view.get('mode') == 'isolated' and view.get('proves') == 'installed-fit':
                errors.append('Isolated views cannot prove installed-fit')
            if not isinstance(view.get('role'), str) or not view['role'].strip():
                errors.append('Inspection views require a role')
            else:
                role = view['role'].strip().lower()
                if role in {'reference-overlay', 'previous-iteration'} or role in seen_roles:
                    errors.append('Inspection roles must be unique render roles')
                seen_roles.add(role)
            if 'retainedNeighbors' in view or view.get('proves') == 'installed-fit':
                neighbors = view.get('retainedNeighbors')
                if not isinstance(neighbors, list) or any(not isinstance(x, str) or not x.strip() for x in neighbors):
                    errors.append('retainedNeighbors must be a list of exact object names')
                elif view.get('proves') == 'installed-fit' and not neighbors:
                    errors.append('Installed-fit inspection requires retainedNeighbors')
    return errors


def inspection_roles(spec):
    return {view['role'].strip().lower(): 'render'
            for plan in spec.get('inspectionPlan', [])
            for view in plan.get('views', [])}


def validate_inspection_evidence(spec, manifest):
    by_role = {r['role'].strip().lower(): r for r in manifest.get('renders', [])}
    for plan in spec.get('inspectionPlan', []):
        for view in plan['views']:
            role = view['role'].strip().lower()
            actual = by_role.get(role, {}).get('roleState', {}).get('inspection')
            if not isinstance(actual, dict):
                raise ValueError(f'{role}: inspection provenance is missing')
            if actual.get('mode') != view['mode']:
                raise ValueError(f'{role}: inspection mode provenance is missing or mismatched')
            if not isinstance(actual.get('disclosure'), str) or not actual['disclosure'].strip():
                raise ValueError(f'{role}: inspection disclosure is required')
            if not isinstance(actual.get('retainedNeighbors', []), list) or any(not isinstance(x, str) for x in actual.get('retainedNeighbors', [])):
                raise ValueError(f'{role}: retainedNeighbors must be a list')
            if set(view.get('retainedNeighbors', [])) - set(actual.get('retainedNeighbors', [])):
                raise ValueError(f'{role}: installed-fit neighbors missing from evidence provenance')
