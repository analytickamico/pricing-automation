#!/bin/bash
echo "=== PAUSAR PRICING AUTOMATION ==="
echo "Data/Hora: $(date)"
echo ""

# Comentar linha do crontab
(crontab -l | sed 's|^\*/10.*pricing.*|#&|') | crontab -

echo "✅ Automação pausada no crontab"
echo ""
echo "Para reativar, execute: ./resume_automation.sh"
echo ""
echo "=== CRONTAB ATUAL ==="
crontab -l | grep pricing
