#!/bin/bash
# Verificação rápida e simples do .dockerignore
# Arquivo: quick_check.sh

echo "🔍 VERIFICAÇÃO RÁPIDA DO .DOCKERIGNORE"
echo "======================================"

# Mostrar arquivos que SERÃO incluídos na imagem
echo "✅ ARQUIVOS QUE VÃO PARA A IMAGEM:"
find . -name "*.py" -o -name "requirements*.txt" | grep -v __pycache__ | sort
echo

# Verificar se arquivos sensíveis estão sendo excluídos
echo "🔒 VERIFICAÇÃO DE SEGURANÇA:"
if [ -f ".env" ]; then
    echo "❌ .env encontrado - deve estar EXCLUÍDO ✅"
else
    echo "✅ .env não encontrado ou excluído"
fi

if [ -f "credentials.json" ]; then
    echo "❌ credentials.json encontrado - deve estar EXCLUÍDO ✅"
else
    echo "✅ credentials.json não encontrado ou excluído"
fi

if [ -f "token.json" ]; then
    echo "⚠️  token.json encontrado - verifique se deve estar excluído"
fi

if [ -d "logs" ]; then
    echo "📁 logs/ encontrado - deve estar EXCLUÍDO ✅"
fi

echo
echo "📊 CONTADORES:"
echo "Scripts .sh: $(find . -name "*.sh" | wc -l) (devem estar excluídos)"
echo "Arquivos Python: $(find . -name "*.py" | wc -l) (devem estar incluídos)"
echo "Arquivos de log: $(find . -name "*.log" | wc -l) (devem estar excluídos)"

echo
echo "🔧 TESTAR BUILD AGORA:"
echo "docker-compose build --no-cache pricing-automation"
