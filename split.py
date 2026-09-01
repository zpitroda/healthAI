import os

path = r'l:\healthAI\app\static\js\app.js'
with open(path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

def write_part(name, start, end):
    with open(f'l:\\healthAI\\app\\static\\js\\{name}', 'w', encoding='utf-8') as f:
        f.writelines(lines[start:end])

# Find the exact indices
def find_idx(substr):
    for i, line in enumerate(lines):
        if substr in line:
            return i
    return -1

idx_ui = find_idx('// DOM ELEMENTS')
idx_api = find_idx('// EVALUATE STACK WITH BACKEND')
idx_copilot = find_idx('// FLAGSHIP AI COPILOT CLIENT ENGINE')

print(f"UI: {idx_ui}, API: {idx_api}, Copilot: {idx_copilot}")

write_part('app-state.js', 0, idx_ui)
write_part('app-ui.js', idx_ui, idx_api)
write_part('app-api.js', idx_api, idx_copilot)
write_part('app-copilot.js', idx_copilot, len(lines))

print("Split complete")
