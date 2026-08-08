from transformers import pipeline

class AIReportGenerator:
    def __init__(self):
        try:
            print("Loading Hugging Face model for exam analysis...")
            self.llm_pipeline = pipeline("text-generation", model="gpt2")
            print("Model loaded successfully.")
        except Exception as e:
            print(f"Error loading LLM: {e}")
            self.llm_pipeline = None

    def generate_professional_summary(self, stats):
        risk = stats.get('risk_score', 0)
        if risk <= 20:
            rec = "No Action Required"
            summary = "The student maintained consistent attention throughout the examination with minimal suspicious activity. No significant malpractice indicators were detected."
        elif risk <= 50:
            rec = "Manual Review Recommended"
            summary = "The student exhibited a small number of suspicious behaviors, including occasional attention deviations. Further review may be recommended."
        else:
            rec = "Strong Evidence of Malpractice"
            summary = "The student demonstrated multiple examination violations, including repeated suspicious activities. Strong evidence of malpractice was detected and administrative review is recommended."
            
        return f"{summary}\n\nRECOMMENDED ACTION: {rec}"

# Global instance
report_generator = AIReportGenerator()

def generate_professional_summary(stats):
    return report_generator.generate_professional_summary(stats)
