# scientia-wiki-init

Scaffolds the on-disk layout scientia depends on. See `SKILL.md`.

## Templates

All scaffolding templates live under `assets/templates/`, mirroring the
target on-disk layout:

```
assets/templates/
├── wiki/
│   ├── index.md.tmpl
│   └── log.md.tmpl
├── development/
│   ├── config.yaml.tmpl
│   └── log.md.tmpl
└── openspec/
    ├── config.yaml.tmpl
    └── schemas/intent-driven/
        ├── schema.yaml.tmpl
        └── README.md.tmpl
```

Each `.tmpl` file uses `{{repo_name}}`, `{{date}}`, `{{now}}`, and
`{{bundle_version}}` placeholders, substituted at copy time by
`scripts/bootstrap.py`.

## Script

`scripts/bootstrap.py` performs the directory creation, template copy,
substitution, and `development/log.md` initialization. It is idempotent
and does not overwrite user-edited files.
