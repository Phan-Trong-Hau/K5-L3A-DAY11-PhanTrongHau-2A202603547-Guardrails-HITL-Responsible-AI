#!/usr/bin/env python3
"""Replay submitted attack prompts against unchanged lab targets; never award points."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


async def replay(args):
    from agents.agent import create_red_agent_default
    from agents.guards_agent import create_red_agent_advance
    from attacks.attacks import run_attacks
    from core.config import get_red_provider, get_red_model
    source = args.input.read_bytes()
    evidence = json.loads(source)
    provider, model = get_red_provider(), get_red_model()
    if (provider, model) != (evidence.get('llm_provider'), evidence.get('llm_model')):
        raise ValueError('Runtime provider/model differs from source evidence; rerun CP4 first')
    key = 'unsafe_attacks' if args.bonus == 'B1' else 'guards_attacks'
    candidates = evidence.get(key, [])
    if not args.all:
        candidates = [row for row in candidates if row.get('leaked') is True]
    if not candidates:
        raise ValueError('No eligible prompts; use --all to test non-leaking prompts')
    target = 'unsafe' if args.bonus == 'B1' else 'guards'
    rows = []
    for attempt in range(1, args.attempts + 1):
        # Fresh target per prompt prevents hidden conversation context in replay.
        for row in candidates:
            agent, runner = (create_red_agent_default() if target == 'unsafe'
                             else create_red_agent_advance())
            results = await run_attacks(agent, runner, prompts=[row],
                                       target_name=target, save_json=False)
            rows.append(dict(results[0], attempt=attempt))
    errors = sum(bool(row.get('error')) or row.get('layer') == 'nemo_error' for row in rows)
    leaks = sum(row['leaked'] for row in rows)
    payload = dict(generated_at=datetime.now(timezone.utc).isoformat(),
                   bonus=args.bonus, target=target, llm_provider=provider, llm_model=model,
                   source_sha256=hashlib.sha256(source).hexdigest(),
                   attempts=args.attempts, results=rows, leaks=leaks, errors=errors,
                   status='reproduced' if leaks else 'error' if errors else 'not_reproduced',
                   default_model_evidence=(provider, model) in {
                       ('openai', 'gpt-4o-mini'), ('gemini', 'gemini-3.5-flash')},
                   official_bonus_confirmed=False,
                   note='Local replay only. Coach/grader decides bonus; choose B1 OR B2.')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in payload.items() if k != 'results'}, indent=2))
    return 2 if errors else 0 if leaks else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bonus', choices=['B1', 'B2'], required=True)
    parser.add_argument('--input', type=Path, default=ROOT / 'outputs/attack_results.json')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--attempts', type=int, choices=range(1, 6), default=1)
    parser.add_argument('--all', action='store_true', help='Replay all prompts, including non-leaks')
    args = parser.parse_args()
    try:
        sys.exit(asyncio.run(replay(args)))
    except (ValueError, OSError) as exc:
        parser.exit(2, f'{exc}\n')
