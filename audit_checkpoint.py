import json
cp = json.load(open('output/checkpoint_v2.json'))
print(f"seen_ids: {len(cp['seen_ids'])}")
print(f"step2_queue roots: {len(cp.get('step2_queue', {}))}")
print(f"step1_roots: {len(cp.get('step1_roots', {}))}")
print(f"Query Progress: {cp.get('query_idx', 0)} / 30")
print(f"Current Step: {cp.get('current_step', 'unknown')}")
print(f"Step 1 Done: {cp.get('step1_done', False)}")
print(f"\nRoot tweet pool ready for Step 2: {list(cp.get('step2_queue', {}).keys())[:5]}...")
