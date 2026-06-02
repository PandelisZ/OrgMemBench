<!-- emergent_evidence pattern=P00 facet=1 2023-10-02 role=emergent_evidence -->

[email_thread] 2023-10-02  

**From:** Arjun Mehta <arjun@helixlogistics.com>  
**To:** Sophia Liu <sophia@helixlogistics.com>, Maya Patel <maya@helixlogistics.com>  
**Cc:** Luis Hernandez <luis@helixlogistics.com>  
**Subject:** New client sandbox setup  

Hi Maya,  

I just finished creating the API keys for the new client in the sandbox environment. I’ve attached the credentials file and the setup guide we used last time.  

Let me know if you need anything else.  

Thanks,  
Arjun  

---  

**From:** Sophia Liu <sophia@helixlogistics.com>  
**To:** Arjun Mehta <arjun@helixlogistics.com>, Maya Patel <maya@helixlogistics.com>  
**Cc:** Luis Hernandez <luis@helixlogistics.com>  
**Subject:** Re: New client sandbox setup  

Arjun, thanks! I’ll push the keys to the repo and update the client’s onboarding doc.  

Maya, could you confirm the client’s callback URL? I’ll need it to finish the integration.  

— Sophia  

---  

**From:** Maya Patel <maya@helixlogistics.com>  
**To:** Sophia Liu <sophia@helixlogistics.com>, Arjun Mehta <arjun@helixlogistics.com>  
**Cc:** Luis Hernandez <luis@helixlogistics.com>  
**Subject:** Re: New client sandbox setup  

Sure thing, Sophia. The callback URL is https://sandbox.clientco.com/api/callback.  

Arjun, can you share the exact steps you used to generate the keys? I want to make sure the process is consistent for the next client.  

Thanks,  
Maya  

---  

**From:** Arjun Mehta <arjun@helixlogistics.com>  
**To:** Maya Patel <maya@helixlogistics.com>, Sophia Liu <sophia@helixlogistics.com>  
**Cc:** Luis Hernandez <luis@helixlogistics.com>  
**Subject:** Re: New client sandbox setup  

Sure, here’s a quick rundown:  

1. Logged into the admin portal.  
2. Navigated to “API Credentials” → “Create New Key.”  
3. Set the key name to “ClientCo Sandbox.”  
4. Copied the public and secret keys into the attached file.  
5. Created a sandbox account in the “Accounts” tab and linked it to the key.  

Let me know if anything looks off.  

— Arjun  

---  

**From:** Luis Hernandez <luis@helixlogistics.com>  
**To:** Arjun Mehta <arjun@helixlogistics.com>, Sophia Liu <sophia@helixlogistics.com>, Maya Patel <maya@helixlogistics.com>  
**Cc:**  
**Subject:** Re: New client sandbox setup  

Thanks for the quick turnaround, team. I’ll ping the client to confirm they can access the sandbox now.  

---  

**Slack #onboarding channel**  

**Arjun:** @Sophia, just pushed the API creds to the repo.  
**Sophia:** Got it. Will update the docs.  
**Maya:** @Arjun, can you double‑check the secret key is not exposed in the public repo?  
**Arjun:** Yep, it’s in the .env file only.  

---  

**End of thread**