<!-- emergent_evidence pattern=P01 facet=1 2020-06-19 role=emergent_evidence -->

[meeting_notes] 2020-06-19  

**Attendees:** Maya Patel (CEO), Luis Hernandez (COO), Arjun Mehta (Senior Engineer), Sophia Liu (Engineering Manager), Miguel Torres (DevOps Engineer), Daniel Kim (VP of Engineering)  

- Maya: “We need to decide on the new API rollout for the West Coast route. Arjun, can you give us a quick status?”  
- Arjun: “We’re at 80% of the feature set. The main blocker is the database migration.”  
- Miguel: “If we push the migration now, the deployment window will be 45 minutes instead of the usual 30. That could push the latency spike into the peak hours.”  
- Sophia: “We can do a staged rollout, but that adds another 15 minutes to the total window.”  
- Daniel: “Let’s keep the window tight. Maya, can we postpone the launch to next week?”  
- Maya: “Fine. Let’s aim for a 2‑hour window next week and keep the latency under 200ms.”  
- Luis: “I’ll update the Ops calendar. Miguel, can you draft the rollback plan?”  
- Miguel: “Sure, I’ll add it to the deployment checklist.”