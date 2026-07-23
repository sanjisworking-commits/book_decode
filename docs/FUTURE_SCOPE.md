# Future Scope

Items below are **out of MVP** unless later explicitly pulled in. Documented so they do not leak into Phase 0–8 implementation by accident.

## Input formats

- PDF input
- OCR for scanned books
- Audiobooks / transcripts
- Multiple simultaneous format uploads

## Product surfaces

- Public book library / catalogue
- Payments and subscriptions
- Community comments and social sharing
- Publisher moderation workflows
- Multi-user collaboration and permissions
- Native mobile applications

## Learning features

- Full spaced-repetition system
- Reflections and active-recall workflows (light versions may be considered only if they do not dilute Argument Spine MVP)
- Notes sync across devices
- Voice interaction

## Intelligence features

- Automatic external research for counters
- Cross-book knowledge graph
- Multi-book comparison
- Author-intent vs reader-critique debate modes beyond the single counter node

## Platform

- PostgreSQL + object storage migration
- Horizontal workers / job queues
- WebSocket progress
- Multi-tenant SaaS auth
- IndicTrans2 as parallel evaluation dashboard
- Recorded LLM fixture mode for offline CI

## Principle

Ship the EPUB → Argument Spine → bilingual interactive map path first. Extend only after acceptance criteria in [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md) are met.
