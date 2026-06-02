<!-- atmosphere slack channel=#customer-xyz 2025-10 role=noise -->

[2025-10-02 09:12] @Sienna Patel: Shipped the auth token refresh bug fix to staging, will push to prod tomorrow. Picking up the pagination refactor next.

[2025-10-02 09:15] @Daniel Ortiz: Any idea why staging is throwing 500s on the shipment lookup endpoint? The logs show a null pointer in the service layer.

[2025-10-02 09:18] @Arjun Mehta: I think it’s the new caching layer. I’ll add a quick test in the PR and ping you when it’s ready.

[2025-10-02 09:45] @Priyanka Desai: Quick heads‑up: I’ll be on PTO next week (Oct 6‑10). I’ll hand over the XYZ tickets to Maya for the duration.

↳ @Maya Rojas: Got it, Priyanka. I’ll keep an eye on the support queue.

[2025-10-02 10:02] @Luis Hernandez: Lunch at the new ramen spot at 12:30? Anyone else want to join?

[2025-10-02 12:15] @Yara Al-Hassan: @Luis, I’m in. Also, can you confirm the API key rotation schedule for the next sprint? I need to update the vendor docs.

[2025-10-02 12:30] @Kenji Sato: Updated the API docs in Notion. FYI, the new “Error Codes” section is in the “API Reference” page. Let me know if anything’s missing.

[2025-10-02 14:55] @Daniel Kim: Deploying to prod in 10 minutes. All green on the health checks. :rocket:

[2025-10-02 15:05] @Daniel Kim: :rotating_light: Rollback done. Back to staging for now. Will investigate the 500s tomorrow.