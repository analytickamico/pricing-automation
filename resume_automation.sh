#!/bin/bash
echo "=== REATIVAR PRICING AUTOMATION ==="
echo "Data/Hora: $(date)"
echo ""

# Descomentar linha do crontab
(crontab -l | sed 's|^#\(.*pricing.*\)|\1|') | crontab -

echo "✅ Automação reativada no crontab"
echo ""
echo "=== CRONTAB ATUAL ==="
crontab -l | grep pricing
