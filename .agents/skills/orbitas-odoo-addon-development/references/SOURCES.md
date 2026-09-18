# Sources — Orbitas Odoo Addon Development Skill v2

Reviewed: **2026-09-18**

## OpenAI / ChatGPT / Codex integration

1. OpenAI Developers — Build skills  
   https://developers.openai.com/docs/build-skills

2. OpenAI Developers — Custom instructions with AGENTS.md  
   https://developers.openai.com/docs/agent-configuration/agents-md

3. OpenAI Developers — Customization overview  
   https://developers.openai.com/docs/customization/overview

4. OpenAI Developers — Skills / plugin concepts  
   https://developers.openai.com/plugins/concepts/skills

5. OpenAI Developers — Building skills for plugins / MCP integration  
   https://developers.openai.com/plugins/build/skills

6. OpenAI Developers Blog — Improving OSS maintenance with skills, AGENTS.md and GitHub Actions  
   https://developers.openai.com/blog/skills-agents-sdk

## Odoo 19 primary sources

7. Odoo 19 — Coding guidelines  
   https://www.odoo.com/documentation/19.0/contributing/development/coding_guidelines.html

8. Odoo 19 — Security in Odoo  
   https://www.odoo.com/documentation/19.0/developer/reference/backend/security.html

9. Odoo 19 — ORM API  
   https://www.odoo.com/documentation/19.0/developer/reference/backend/orm.html

10. Odoo 19 — Performance  
    https://www.odoo.com/documentation/19.0/developer/reference/backend/performance.html

11. Odoo 19 — Multi-company Guidelines  
    https://www.odoo.com/documentation/19.0/developer/howtos/company.html

12. Odoo 19 — Testing Odoo  
    https://www.odoo.com/documentation/19.0/developer/reference/backend/testing.html

13. Odoo 19 — CLI / test selection  
    https://www.odoo.com/documentation/19.0/developer/reference/cli.html

14. Odoo 19 — Module manifests  
    https://www.odoo.com/documentation/19.0/developer/reference/backend/module.html

15. Odoo 19 — Web controllers  
    https://www.odoo.com/documentation/19.0/developer/reference/backend/http.html

16. Odoo 19 — External JSON-2 API  
    https://www.odoo.com/documentation/19.0/developer/reference/external_api.html

17. Odoo 19 — External RPC API / deprecation notice  
    https://www.odoo.com/documentation/19.0/developer/reference/external_rpc_api.html

18. Odoo 19 — Frontend services  
    https://www.odoo.com/documentation/19.0/developer/reference/frontend/services.html

19. Odoo 19 — Frontend framework overview  
    https://www.odoo.com/documentation/19.0/developer/reference/frontend/framework_overview.html

20. Odoo 19 — JavaScript reference / registries / patching  
    https://www.odoo.com/documentation/19.0/developer/reference/frontend/javascript_reference.html

21. Odoo 19 — Assets  
    https://www.odoo.com/documentation/19.0/developer/reference/frontend/assets.html

22. Odoo 19 — Upgrade a customized database  
    https://www.odoo.com/documentation/19.0/developer/howtos/upgrade_custom_db.html

23. Odoo 19 — Upgrade scripts  
    https://www.odoo.com/documentation/19.0/developer/reference/upgrades/upgrade_scripts.html

24. Odoo 19 — Odoo.sh custom modules  
    https://www.odoo.com/documentation/19.0/administration/odoo_sh/getting_started/create.html

25. Odoo 19 — Licenses  
    https://www.odoo.com/documentation/19.0/legal/licenses.html

## Community / OCA references

26. OCA Addons Repo Template  
    https://github.com/OCA/oca-addons-repo-template

27. OCA pylint-odoo  
    https://github.com/OCA/pylint-odoo

28. OCA Maintainer Tools  
    https://github.com/OCA/maintainer-tools

## Project-specific basis

- Orbitas uses Odoo as the reference ERP connector before other ERP connectors.
- ERP adapters normalize source-system objects into a common Orbitas domain model instead of leaking Odoo/QBO/1C objects into clearing core.
- Clearing discovery produces candidate paths/proposals; execution requires policy/consent and current-state validation.
- Orbitas settlement uses redirect/payment-instruction semantics rather than assuming automatic novation.
- A remote settlement instruction must not be equated with Odoo accounting discharge without an explicit accounting workflow.
