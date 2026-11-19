"""Terminal demo using the real agent factories; history is never LLM context."""
from __future__ import annotations

import argparse
import asyncio
import json

from demo_history import DemoHistory


class DemoApp:
    def __init__(self, target='blue', history=None, user_id='demo-user'):
        from agents.agent import create_blue_agent, create_red_agent_default
        from agents.guards_agent import create_red_agent_advance
        from assignment.pipeline import build_production_plugins
        from core.config import get_blue_provider, get_blue_model, get_red_provider, get_red_model
        self.target = target
        self.history = history if history is not None else DemoHistory()
        self.plugins = build_production_plugins() if target == 'blue' else []
        factory = {'red': create_red_agent_default, 'advance': create_red_agent_advance}
        self.agent, self.runner = (create_blue_agent(self.plugins) if target == 'blue'
                                   else factory[target]())
        self.runner.user_id = user_id
        self.provider = get_blue_provider() if target == 'blue' else get_red_provider()
        self.model = get_blue_model() if target == 'blue' else get_red_model()

    async def ask(self, prompt):
        from core.utils import chat_with_agent
        from attacks.attacks import classify_attack_outcome
        before = [p.blocked_count for p in self.plugins]
        redactions = getattr(self.plugins[-1], 'redacted_count', 0) if self.plugins else 0
        try:
            response, _ = await chat_with_agent(self.agent, self.runner, prompt)
        except Exception as exc:
            # Provider errors may contain request data; store only exception type.
            self.history.append(target=self.target, provider=self.provider, model=self.model,
                                input=prompt, response=type(exc).__name__,
                                blocked=True, layer='model_error')
            raise RuntimeError(f'Model request failed ({type(exc).__name__})') from None
        outcome = classify_attack_outcome(prompt, response,
                    target_name={'red': 'unsafe', 'advance': 'guards', 'blue': 'blue'}[self.target])
        layer = next((p.name for p, count in zip(self.plugins, before)
                      if p.blocked_count > count), outcome['layer'])
        if self.plugins and self.plugins[-1].redacted_count > redactions:
            layer = 'output_guardrail'
        row = dict(target=self.target, provider=self.provider, model=self.model,
                   input=prompt, response=response, blocked=(layer not in (None, 'leaked')) or outcome['blocked'],
                   layer=layer, leaked=outcome['leaked'])
        row['history_id'] = self.history.append(**row)
        return row


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=['blue', 'red', 'advance'], default='blue')
    parser.add_argument('--prompt', help='One request; omit for interactive mode')
    parser.add_argument('--history', action='store_true', help='Show redacted history without API calls')
    parser.add_argument('--clear-history', action='store_true')
    args = parser.parse_args()
    history = DemoHistory()
    if args.clear_history:
        history.clear()
        return
    if args.history:
        print(json.dumps(history.list(), ensure_ascii=False, indent=2))
        return
    app = DemoApp(args.target, history)
    if args.prompt is not None:
        print(json.dumps(await app.ask(args.prompt), ensure_ascii=False, indent=2))
        return
    print(f'{app.target}: {app.provider}/{app.model}. /history, /quit. Each request is independent.')
    while True:
        try:
            prompt = input('You> ')
        except (EOFError, KeyboardInterrupt):
            break
        if prompt == '/quit':
            break
        if prompt == '/history':
            print(json.dumps(history.list(), ensure_ascii=False, indent=2))
            continue
        try:
            row = await app.ask(prompt)
            print(f"[{row['layer'] or 'reply'}] {row['response']}")
        except RuntimeError as exc:
            print(exc)


if __name__ == '__main__':
    asyncio.run(main())
