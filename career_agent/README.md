# Career Agent - AgentOS

**Version 1.0**

The **Career Agent** is an autonomous AI career advisor within AgentOS responsible for analyzing professional profiles, resumes, skills, and project portfolios to generate ATS evaluations, skill gap analysis, and 1-year career roadmaps.

## 18-Step Career Evaluation Pipeline
1. Input Type Identification
2. Candidate Profile Extraction
3. Professional Career Summary (max 6 sentences)
4. Skill Analysis (Technical, Soft, Missing, Level)
5. Resume Structure & Completeness Evaluation
6. ATS Evaluation (0-100 Score & Remarks)
7. Skill Gap Analysis
8. Learning Path Recommendations
9. Career Roles Recommendation
10. Internship Domains Recommendation
11. Certifications Recommendation
12. Project & Portfolio Quality Analysis
13. 1-Year Growth Roadmap (Immediate, 3M, 6M, 1Y)
14. Candidate Weaknesses Identification
15. Candidate Strengths Identification
16. Employability Score (0-100)
17. Prioritized Recommendations
18. Confidence Score (0.0 to 1.0)

## API Provider & Key
Configured to use `GROQ_API_KEY3` (`llama-3.3-70b-versatile`).

## Running locally

```bash
# 1. Initialize Database
python init_db.py

# 2. Start Career Agent Server
python server.py
```
