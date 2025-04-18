#!/bin/bash

# Fail if not using bash
if [ -z "$BASH_VERSION" ]; then
  echo "❌ This script must be run with bash."
  exit 1
fi

API_URL="http://localhost:5001/chat"
LOG_FILE="rag_agent_test_results_$(date +%Y%m%d_%H%M%S).log"

# Topics and matching questions
TOPICS=(
  "401(k) / Rollover"
  "401(k) / Rollover"
  "Short-Term Disability (STD)"
  "Short-Term Disability (STD)"
  "Health Savings Account (HSA) / Preventive Meds"
  "Health Savings Account (HSA) / Preventive Meds"
  "Mental Health"
  "Mental Health"
  "Well-being"
  "Well-being"
  "Open Enrollment"
  "Open Enrollment"
  "Retirement and Financial Planning"
  "Retirement and Financial Planning"
  "New Hire General"
  "New Hire General"
  "Family Status Changes"
  "Family Status Changes"
  "Pricing and Payroll"
  "Pricing and Payroll"
  "CA Disability / Paid Family Leave"
  "CA Disability / Paid Family Leave"
  "Long-Term Disability (LTD)"
  "Long-Term Disability (LTD)"
)

QUESTIONS=(
  "What are the two rollover options when transferring funds into the Oracle 401(k) Plan?"
  "How should a check be made out for a rollover into Fidelity for Oracle’s plan?"
  "How is 'Disability' defined in the Oracle STD Benefit Plan?"
  "What is the elimination period before STD benefits begin?"
  "Which preventive medications are covered before meeting the deductible in 2025?"
  "What is the difference between Tier 1 and Tier 3 medications in the UHC drug list?"
  "What mental health services does Oracle offer through the Employee Assistance Program?"
  "How can Oracle employees access Calm or Calm Health for mental well-being?"
  "What does Oracle's Wellhub program include and how do employees sign up?"
  "What is included in the free Starter Plan for Wellhub offered by Oracle?"
  "What are the key deadlines and actions required during Oracle’s 2025 Open Enrollment?"
  "What happens if I don’t take any action during the open enrollment period?"
  "What financial planning services does Oracle offer through Ayco and Fidelity?"
  "How can employees schedule a one-on-one retirement consultation with Fidelity?"
  "What are the benefits enrollment deadlines for new Oracle employees?"
  "What happens if a new hire forgets to enroll in benefits within 31 days?"
  "What types of family status changes allow me to update Oracle benefit elections mid-year?"
  "If I have a child, how soon must I report the birth to update my benefits?"
  "What are the biweekly premium costs for the HSA Medical Plan for full-time employees in 2025?"
  "How do benefit deductions change with Oracle’s switch to biweekly pay in 2025?"
  "What is the waiting period for receiving CA Voluntary Disability benefits?"
  "How does Paid Family Leave differ from Disability benefits in Oracle’s California VDI plan?"
  "Does LTD coverage vary by state, and where can employees find state-specific notices?"
  "What medical conditions count as 'Complications of Pregnancy' under California LTD law?"
)

echo "📋 Oracle Benefits RAG Agent Test — $(date)" | tee -a "$LOG_FILE"
echo "-----------------------------------------------------" | tee -a "$LOG_FILE"

for i in "${!QUESTIONS[@]}"; do
  TOPIC="${TOPICS[$i]}"
  QUESTION="${QUESTIONS[$i]}"
  echo -e "\n🧩 Topic: $TOPIC" | tee -a "$LOG_FILE"
  echo "❓ Question: $QUESTION" | tee -a "$LOG_FILE"

  RESPONSE=$(curl -s -X POST "$API_URL" \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"$QUESTION\"}")

  # Extract fields using jq
  ANSWER=$(echo "$RESPONSE" | jq -r '.answer // "No answer returned."')
  SOURCES=$(echo "$RESPONSE" | jq -r '.sources | join(", ")')

  echo "💬 Answer: $ANSWER" | tee -a "$LOG_FILE"
  echo "📂 Source PDFs: $SOURCES" | tee -a "$LOG_FILE"
  echo "-----------------------------------------------------" | tee -a "$LOG_FILE"
done

echo -e "\n✅ Test completed. Log saved to $LOG_FILE"
