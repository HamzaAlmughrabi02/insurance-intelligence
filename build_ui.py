"""Deterministic UI build. One router and renderer; no legacy wrapper stack."""
from pathlib import Path
root=Path(__file__).resolve().parent
scripts=['workspace-state.js','workspace-auth.js','report-views.js','workspace-reader.js','workspace-ui.js']
s=(root/'workspace.html').read_text(encoding='utf-8')
s=s.replace('<!-- WORKSPACE_STYLES -->','<style>'+ '\n'.join((root/n).read_text(encoding='utf-8') for n in ['v2-report.css','workspace.css'])+'</style>')
s=s.replace('<!-- WORKSPACE_SCRIPTS -->','<script>'+ '\n'.join((root/n).read_text(encoding='utf-8') for n in scripts)+'</script>')
(root/'index.html').write_text(s,encoding='utf-8')
print('Built unified V2 case workspace.')
