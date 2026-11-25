---
pagination:
  data: spec
  size: 1
  alias: specDoc
  addAllPagesToCollections: true
templateEngineOverride: njk,md
---
{{ specDoc.markdown | safe }}
