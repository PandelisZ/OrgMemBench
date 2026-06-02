<!-- atmosphere slack channel=#salesforce-deals 2024-02 role=noise -->

[2024-02-03 09:12] @Maya Rojas: Shipped the new discount logic to prod, testing on staging now. Next up: tweak the email template for renewal reminders.  
[2024-02-03 09:15] @Priyanka Desai ↳ @Maya Rojas: Got it, will ping you when the test data is ready.  
[2024-02-03 10:05] @Victor Chen: Anyone know why staging is throwing 500s on the shipment API? I hit the same error after the last deploy.  
[2024-02-03 10:12] @Daniel Ortiz ↳ @Victor Chen: Looks like the new validation rule is missing a null check. I’ll add a quick fix in the PR.  
[2024-02-03 12:30] @Leila Hassan: Lunch at the new café on 5th? Anyone?  
[2024-02-03 12:45] @Sienna Patel: Count me in, but I’m on a call until 1pm.  
[2024-02-04 15:00] @Maya Patel: FYI, I’ll be on PTO next week (Feb 11-15). Will hand over the Q1 pipeline review to Maya Rojas.  
[2024-02-04 15:05] @Maya Rojas: Thanks for the heads‑up, Maya. I’ll keep the deck updated.  
[2024-02-04 16:20] @Sophia Liu: Deploying to prod in 10 minutes. All green on the health checks.  
[2024-02-04 16:30] @Sophia Liu: :rotating_light: Rollback done, back to staging. Will investigate the issue.  
[2024-02-04 17:00] @Nisha Gupta: Quick question—do we have the latest cost‑center mapping for the new clients in the Salesforce import?  
[2024-02-04 17:05] @Mei Lin ↳ @Nisha Gupta: Yes, updated the mapping sheet in Notion. Check the “Client Onboarding” page.  
[2024-02-04 17:10] @Fatima Al‑Mansouri: Just a reminder that the NDA template in #legal‑docs needs a clause update for data residency.  
[2024-02-04 17:15] @Rajesh Patel: Hey team, I’ve posted a new job ad for a mid‑level dev in #recruiting. Let me know if you see any good candidates.  
[2024-02-04 17:20] @Priyanka Desai: Got the ad, Rajesh. Will circulate it in the next CS meeting.  
[2024-02-04 17:25] @Victor Chen: Back to the 500s—found a missing environment variable. Fixed it, pushing a hotfix PR.  
[2024-02-04 17:30] @Victor Chen: Will keep you posted.  
[2024-02-04 17:35] @Maya Rojas: Thanks, Victor. That should clear the staging errors.  
[2024-02-04 17:40] @Leila Hassan: Anyone else want to grab a coffee after the meeting?  
[2024-02-04 17:45] @Sienna Patel: Sure, I’ll be free after 5pm.  
[2024-02-04 17:50] @Maya Patel: Great, see you all later.