# heta dynamic-insert

Control whether `heta insert` uses dynamic LLM wiki merging.

```bash
heta dynamic-insert status
heta dynamic-insert on
heta dynamic-insert off
```

Default after `heta init` is off. With dynamic insert off, `heta insert`
uses static insertion: the LLM writes only the page summary, while Little Heta
writes the page structure, source section, index, log, Git commit, and vector
index updates.

Turn dynamic insert on to use the older tool-calling merge agent that can read
existing pages, update related pages, and merge a new document into an existing
topic page.
