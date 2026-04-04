"""
Outreach Planner Agent
Plans email/SMS outreach sequences based on lead score and profile
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import random

from app.core.logging import get_logger
from app.agents.base import BaseAgent, retry_on_failure
from app.tools.llm_failover import get_llm_client

logger = get_logger(__name__)


class OutreachPlannerAgent(BaseAgent):
    """
    Agent responsible for planning outreach sequences
    Creates personalized email templates and scheduling plans
    """
    
    def __init__(self):
        super().__init__(name="outreach_planner", version="1.0.0")
        self.llm_client = get_llm_client()
        
        # Outreach templates by lead quality
        self.templates = {
            "hot": {
                "subject": "Exciting opportunity at {company_name}",
                "delay_days": 0,
                "followup_days": [2, 5, 10]
            },
            "warm": {
                "subject": "Thought you might find this interesting",
                "delay_days": 1,
                "followup_days": [3, 7, 14]
            },
            "cold": {
                "subject": "Quick question about {company_name}",
                "delay_days": 2,
                "followup_days": [5, 10, 20]
            }
        }
    
    @retry_on_failure(max_retries=2)
    async def process(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create outreach plan for a single lead
        """
        self.log_step("planning_outreach", {"email": lead.get("email"), "quality": lead.get("quality")})
        
        quality = lead.get("quality", "cold")
        score = lead.get("score", 0)
        company = lead.get("company_name", "")
        job_title = lead.get("job_title", "")
        first_name = lead.get("first_name", "") or lead.get("full_name", "").split()[0] if lead.get("full_name") else "there"
        
        # Get base template configuration
        template_config = self.templates.get(quality, self.templates["cold"])
        
        # Generate personalized email content using AI for hot/warm leads
        if quality in ["hot", "warm"] and score >= 60:
            email_content = await self._generate_ai_email(lead, first_name, company)
        else:
            email_content = self._generate_template_email(lead, first_name, company, job_title)
        
        # Create outreach sequence
        sequence = self._create_sequence(
            lead=lead,
            first_name=first_name,
            template_config=template_config,
            email_content=email_content
        )
        
        # Add outreach plan to lead
        lead["outreach_plan"] = {
            "quality": quality,
            "score": score,
            "primary_template": email_content,
            "sequence": sequence,
            "recommended_channel": "email",
            "best_time_to_contact": self._get_best_contact_time(lead),
            "personalization_tips": self._get_personalization_tips(lead)
        }
        
        self.logger.info(f"Outreach plan created for {lead.get('email')}: {quality} quality")
        
        return lead
    
    async def plan_batch(
        self,
        leads: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Create outreach plans for multiple leads
        """
        self.logger.info(f"Planning outreach for {len(leads)} leads")
        return await self.process_batch(leads)
    
    async def _generate_ai_email(
        self,
        lead: Dict[str, Any],
        first_name: str,
        company: str
    ) -> Dict[str, Any]:
        """
        Generate personalized email using AI
        """
        try:
            prompt = f"""
Create a personalized cold email for this lead:

Lead Information:
- Name: {first_name}
- Company: {company}
- Job Title: {lead.get('job_title', 'Unknown')}
- Industry: {lead.get('industry', 'Unknown')}
- Lead Score: {lead.get('score', 0)}/100

Our Company: LeadGen System (AI-powered lead generation platform)

Requirements:
1. Subject line (max 60 chars)
2. Body (max 200 words)
3. Call to action
4. Personalization based on their role/company

Return JSON with: subject, body, cta
"""
            response = await self.llm_client.complete_with_json(
                prompt=prompt,
                temperature=0.7,
                max_tokens=500
            )
            
            return {
                "subject": response.get("subject", f"Quick question about {company}"),
                "body": response.get("body", ""),
                "cta": response.get("cta", "Would you be open to a quick chat?"),
                "generated_by": "ai"
            }
            
        except Exception as e:
            logger.error(f"AI email generation failed: {e}")
            return self._generate_template_email(lead, first_name, company, lead.get('job_title', ''))
    
    def _generate_template_email(
        self,
        lead: Dict[str, Any],
        first_name: str,
        company: str,
        job_title: str
    ) -> Dict[str, Any]:
        """
        Generate template-based email
        """
        templates = {
            "cto": f"Hi {first_name},\n\nI've been following {company}'s work in the tech space. As CTO, you're likely always looking for ways to optimize lead generation.\n\nOur AI platform helps companies like yours automate lead discovery with 90% accuracy.\n\nWould you be open to a 15-min demo?",
            "ceo": f"Hi {first_name},\n\nCongratulations on the growth at {company}. As CEO, I know your time is valuable.\n\nWe help CEOs like you automate lead generation and focus on what matters - closing deals.\n\nInterested in seeing how?",
            "default": f"Hi {first_name},\n\nI hope you're doing well. I noticed {company} is doing great things in {lead.get('industry', 'your industry')}.\n\nWe help businesses generate qualified leads automatically using AI.\n\nWould you be interested in learning more?"
        }
        
        # Select template based on job title
        job_lower = (job_title or "").lower()
        if "cto" in job_lower or "chief technology" in job_lower:
            body = templates["cto"]
        elif "ceo" in job_lower or "chief executive" in job_lower:
            body = templates["ceo"]
        else:
            body = templates["default"]
        
        return {
            "subject": f"Quick question about {company}",
            "body": body,
            "cta": "Would you be available for a quick chat next week?",
            "generated_by": "template"
        }
    
    def _create_sequence(
        self,
        lead: Dict[str, Any],
        first_name: str,
        template_config: Dict[str, Any],
        email_content: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Create full outreach sequence
        """
        sequence = []
        
        # Initial email
        sequence.append({
            "step": 1,
            "type": "email",
            "delay_days": template_config["delay_days"],
            "scheduled_date": (datetime.utcnow() + timedelta(days=template_config["delay_days"])).isoformat(),
            "subject": email_content["subject"],
            "content": email_content["body"],
            "cta": email_content["cta"]
        })
        
        # Follow-up emails
        for i, delay in enumerate(template_config["followup_days"], start=2):
            followup_content = self._generate_followup_email(first_name, i-1)
            sequence.append({
                "step": i,
                "type": "email",
                "delay_days": delay,
                "scheduled_date": (datetime.utcnow() + timedelta(days=delay)).isoformat(),
                "subject": f"Re: {email_content['subject']}",
                "content": followup_content["body"],
                "cta": followup_content["cta"]
            })
        
        return sequence
    
    def _generate_followup_email(self, first_name: str, followup_number: int) -> Dict[str, Any]:
        """
        Generate follow-up email content
        """
        followups = [
            {
                "body": f"Hi {first_name},\n\nJust wanted to follow up on my previous message. Would love to chat about how we can help your team.\n\nLet me know if you have 15 mins this week.",
                "cta": "Available for a quick call?"
            },
            {
                "body": f"Hi {first_name},\n\nThought I'd share a case study of how we helped a similar company generate 500+ qualified leads in their first month.\n\nWorth a look?",
                "cta": "Send me the case study"
            },
            {
                "body": f"Hi {first_name},\n\nOne last try - I really think our platform could add value to {first_name}'s team.\n\nHappy to jump on a quick call whenever works for you.",
                "cta": "Open to a quick chat?"
            }
        ]
        
        return followups[followup_number - 1] if followup_number <= len(followups) else followups[-1]
    
    def _get_best_contact_time(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine best time to contact based on location
        """
        location = lead.get("location", "").lower()
        
        # Timezone mapping (simplified)
        if any(city in location for city in ["new york", "boston", "miami"]):
            timezone = "EST"
            best_hours = "10am - 12pm EST"
        elif any(city in location for city in ["san francisco", "seattle", "los angeles"]):
            timezone = "PST"
            best_hours = "10am - 12pm PST"
        elif any(city in location for city in ["london", "manchester"]):
            timezone = "GMT"
            best_hours = "10am - 12pm GMT"
        else:
            timezone = "Local"
            best_hours = "10am - 12pm local time"
        
        return {
            "timezone": timezone,
            "best_hours": best_hours,
            "best_days": ["Tuesday", "Wednesday", "Thursday"]
        }
    
    def _get_personalization_tips(self, lead: Dict[str, Any]) -> List[str]:
        """
        Generate personalization tips for outreach
        """
        tips = []
        
        if lead.get("company_name"):
            tips.append(f"Mention their recent achievement at {lead['company_name']}")
        
        if lead.get("job_title"):
            tips.append(f"Reference their role as {lead['job_title']} and related challenges")
        
        if lead.get("linkedin_url"):
            tips.append("Check their recent LinkedIn activity for conversation starters")
        
        if lead.get("industry"):
            tips.append(f"Discuss {lead['industry']} industry trends")
        
        return tips[:3]  # Max 3 tips


# Singleton instance
_outreach_planner = None


def get_outreach_planner() -> OutreachPlannerAgent:
    """Get or create outreach planner instance"""
    global _outreach_planner
    if _outreach_planner is None:
        _outreach_planner = OutreachPlannerAgent()
    return _outreach_planner