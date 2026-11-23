from pathlib import Path
root=Path(__file__).resolve().parent
p=root/'index.html'
s=p.read_text(encoding='utf-8')
s=s.replace('✦ تصميم تجريبي · v0.4','تشغيل محلي · مراجعة بشرية')
s=s.replace("'\"':'&quot;'}", "'\"':'&quot;',\"'\":'&#39;'}")
marker='<!-- insurance-integration-extension -->'
if marker in s:s=s.split(marker)[0]+'</body></html>'
s=s.replace('<body>','<body class="auth-pending">')
if '.auth-pending .shell' not in s:s=s.replace('</style>','.auth-pending .shell{display:none} #account-entry{padding:16px}</style>')
scripts='\n'.join((root/name).read_text(encoding='utf-8') for name in ['ui-extension.js','auth-ui.js','evidence-review.js','review-center.js'])
review_css='<style id="review-center-styles">'+(root/'review-center.css').read_text(encoding='utf-8')+'</style>'
s=__import__('re').sub(r'<style id="review-center-styles">.*?</style>','',s,flags=__import__('re').S)
s=s.replace('</head>',review_css+'</head>')
s=s.replace('</head>','<style id="evidence-review-styles">'+(root/'evidence-review.css').read_text(encoding='utf-8')+'</style></head>') if 'id="evidence-review-styles"' not in s else __import__('re').sub(r'<style id="evidence-review-styles">.*?</style>','<style id="evidence-review-styles">'+(root/'evidence-review.css').read_text(encoding='utf-8')+'</style>',s,flags=__import__('re').S)
s=s.replace('</body>',marker+'<script>\n'+scripts+'\n</script></body>')
p.write_text(s,encoding='utf-8')
print('Updated existing UI with evidence, correction, history and retry actions.')
