from pypdf import PdfReader
import json, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
out = {}
for lang, path in [("en","rules-en-ihf-2024.pdf"),("de","rules-de-dhb-2025.pdf")]:
    rd = PdfReader(path)
    out[lang] = "\n".join((p.extract_text() or "") for p in rd.pages)
    print(lang, len(rd.pages), "pages", len(out[lang]), "chars")
open("_fulltext.json","w").write(json.dumps(out))
