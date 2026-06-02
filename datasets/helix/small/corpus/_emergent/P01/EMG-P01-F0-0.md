<!-- emergent_evidence pattern=P01 facet=0 2021-04-26 role=emergent_evidence -->

[slack_thread] 2021-04-26  
**#arch-decision**  

**Arjun Mehta** 10:12 AM  
> @Sophia Liu, @Daniel Kim – attached the proposal for the new shipment‑status webhook integration. I’ve sketched the flow and linked the relevant API spec in the doc. Let me know if the auth flow looks solid.  

**Sophia Liu** 10:15 AM  
> Thanks Arjun. I’ll review the spec and ping you if I spot any gaps.  

**Daniel Kim** 10:18 AM  
> Looks good to me. Will loop in Miguel for the deployment checklist.  

**Miguel Torres** 10:20 AM  
> Got it. I’ll pull the spec and add the CI steps.  

**Arjun Mehta** 10:22 AM  
> @Miguel, here’s the spec link: https://api.helix.com/docs/webhooks#shipment-status. The auth uses OAuth2 with PKCE.  

**Sophia Liu** 10:25 AM  
> Great, thanks Arjun. Will draft the README for the team.  

**Luis Hernandez** 10:30 AM  
> Quick question – do we need to update the SLA docs for this new webhook?  

**Arjun Mehta** 10:32 AM  
> The SLA impact is minimal; just a 2‑second latency window. I’ll add a note to the SLA doc.  

**Maya Patel** 10:35 AM  
> Thanks for the quick turnaround, team. Let’s keep the momentum.