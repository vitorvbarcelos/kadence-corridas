#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import sys
from datetime import datetime
from utils import salvar_eventos, limpar_csv, criar_backup
from scrapers.time_ticket_scraper import extrair_timeticket
from scrapers.ticket_sports_scraper import extrair_ticket_sports
from scrapers.sympla_scraper import extrair_sympla
from scrapers.even3_scraper import extrair_even3
from scrapers.doity_scraper import extrair_doity
from scrapers.atletis_scraper import extrair_atletis
from scrapers.central_corrida_scraper import extrair_central_corrida
from scrapers.minhas_inscricoes_scraper import extrair_minhas_inscricoes
from scrapers.ativo_scraper import extrair_ativo
from scrapers.corridao_scraper import extrair_corridao
from scrapers.youmovin_scraper import extrair_youmovin
from scrapers.cronoschip_scraper import extrair_cronoschip
from scrapers.brasilcorrida_scraper import extrair_brasilcorrida
from scrapers.vemcorrer_scraper import extrair_vemcorrer
from scrapers.sporttimer_scraper import extrair_sporttimer
from scrapers.oxyscrono_scraper import extrair_oxyscrono
from scrapers.liverun_scraper import extrair_liverun
from scrapers.trackfield_scraper import extrair_trackfield

def validar_ambiente():
    """Verifica ambiente e cria diretórios necessários"""
    if not os.path.exists("data"):
        os.makedirs("data")
    try:
        import playwright
    except ImportError:
        print("❌ Playwright não encontrado. Execute: pip install playwright")
        sys.exit(1)

def consolidar_eventos_globais(*args_eventos):
    """Consolida eventos de todas as fontes removendo duplicatas"""
    todos_eventos = []
    for eventos in args_eventos:
        if eventos:
            todos_eventos.extend(eventos)
    
    # Remove duplicatas por hash
    eventos_unicos = {}
    for evento in todos_eventos:
        hash_evento = evento.get('hash')
        if hash_evento and hash_evento not in eventos_unicos:
            eventos_unicos[hash_evento] = evento
    
    eventos_finais = list(eventos_unicos.values())
    
    # Ordena por data
    def ordenar_por_data(evento):
        try:
            if 'data_obj' in evento and evento['data_obj']:
                return evento['data_obj']
            data_str = evento.get('data', '01/01/2030')
            return datetime.strptime(data_str, '%d/%m/%Y')
        except:
            return datetime(2030, 1, 1)
    
    eventos_finais.sort(key=ordenar_por_data)
    return eventos_finais

def executar_fonte(nome, funcao_extrair):
    """Executa uma fonte de scraping"""
    try:
        eventos = funcao_extrair()
        if eventos:
            print(f"✅ {nome}: {len(eventos)} eventos")
            return eventos
        else:
            print(f"⚠️ {nome}: 0 eventos")
            return []
    except Exception as e:
        print(f"❌ {nome}: Falhou")
        return []

def executar_scraping_completo():
    """Executa scraping de todas as fontes"""
    print("🚀 Iniciando coleta de 19 fontes...")
    
    fontes = [
        ("TimeTicket", extrair_timeticket),
        ("TicketSports", extrair_ticket_sports),
        ("Sympla", extrair_sympla),
        ("Even3", extrair_even3),
        ("Doity", extrair_doity),
        ("Atletis", extrair_atletis),
        ("Central Corrida", extrair_central_corrida),
        ("Minhas Inscrições", extrair_minhas_inscricoes),
        ("Ativo.com", extrair_ativo),
        ("Corridão.com", extrair_corridao),
        ("YouMovin.com", extrair_youmovin),
        ("Cronoschip.com", extrair_cronoschip),
        ("BrasilCorrida.com", extrair_brasilcorrida),
        ("VemCorrer.com", extrair_vemcorrer),
        ("SportTimer.com", extrair_sporttimer),
        ("OxyScrono.com", extrair_oxyscrono),
        ("LIVE! Run", extrair_liverun),
        ("Track&Field", extrair_trackfield)
    ]
    
    todos_eventos = []
    sucessos = 0
    
    for nome, funcao in fontes:
        eventos = executar_fonte(nome, funcao)
        if eventos:
            todos_eventos.extend(eventos)
            sucessos += 1
    
    return todos_eventos, sucessos, len(fontes)

def exibir_relatorio_final(eventos, sucessos, total_fontes, tempo):
    """Exibe relatório final consolidado"""
    print(f"\n📊 RELATÓRIO FINAL:")
    
    # Por fonte
    fontes_count = {}
    for evento in eventos:
        fonte = evento.get('fonte', 'Desconhecida')
        fontes_count[fonte] = fontes_count.get(fonte, 0) + 1
    
    for fonte, count in sorted(fontes_count.items()):
        print(f"   {fonte}: {count}")
    
    print(f"\n🏆 Total: {len(eventos)} eventos únicos")
    print(f"⏱️ Tempo: {tempo:.1f}s | Taxa: {sucessos}/{total_fontes}")

def main():
    parser = argparse.ArgumentParser(description="Scraper multi-plataforma de eventos de corrida")
    
    parser.add_argument("--limpar", action="store_true", help="Limpa CSV antes")
    parser.add_argument("--backup", action="store_true", help="Cria backup antes")
    
    # Fontes individuais
    parser.add_argument("--timeticket-only", action="store_true")
    parser.add_argument("--ticketsports-only", action="store_true")
    parser.add_argument("--sympla-only", action="store_true")
    parser.add_argument("--even3-only", action="store_true")
    parser.add_argument("--doity-only", action="store_true")
    parser.add_argument("--atletis-only", action="store_true")
    parser.add_argument("--central-corrida-only", action="store_true")
    parser.add_argument("--minhas-inscricoes-only", action="store_true")
    parser.add_argument("--ativo-only", action="store_true")
    parser.add_argument("--corridao-only", action="store_true")
    parser.add_argument("--youmovin-only", action="store_true")
    parser.add_argument("--cronoschip-only", action="store_true")
    parser.add_argument("--brasilcorrida-only", action="store_true")
    parser.add_argument("--vemcorrer-only", action="store_true")
    parser.add_argument("--sporttimer-only", action="store_true")
    parser.add_argument("--oxyscrono-only", action="store_true")
    parser.add_argument("--liverun-only", action="store_true")
    parser.add_argument("--trackfield-only", action="store_true")
    
    args = parser.parse_args()
    
    validar_ambiente()
    
    if args.backup:
        criar_backup()
    
    if args.limpar:
        limpar_csv()
        print("🧹 CSV limpo")
    
    start_time = datetime.now()
    
    # Execução individual
    fontes_individuais = {
        'timeticket_only': ("TimeTicket", extrair_timeticket),
        'ticketsports_only': ("TicketSports", extrair_ticket_sports),
        'sympla_only': ("Sympla", extrair_sympla),
        'even3_only': ("Even3", extrair_even3),
        'doity_only': ("Doity", extrair_doity),
        'atletis_only': ("Atletis", extrair_atletis),
        'central_corrida_only': ("Central Corrida", extrair_central_corrida),
        'minhas_inscricoes_only': ("Minhas Inscrições", extrair_minhas_inscricoes),
        'ativo_only': ("Ativo.com", extrair_ativo),
        'corridao_only': ("Corridão.com", extrair_corridao),
        'youmovin_only': ("YouMovin.com", extrair_youmovin),
        'cronoschip_only': ("Cronoschip.com", extrair_cronoschip),
        'brasilcorrida_only': ("BrasilCorrida.com", extrair_brasilcorrida),
        'vemcorrer_only': ("VemCorrer.com", extrair_vemcorrer),
        'sporttimer_only': ("SportTimer.com", extrair_sporttimer),
        'oxyscrono_only': ("OxyScrono.com", extrair_oxyscrono),
        'liverun_only': ("LIVE! Run", extrair_liverun),
        'trackfield_only': ("Track&Field", extrair_trackfield)
    }
    
    # Verifica se é execução individual
    fonte_individual = None
    for arg_name, (nome, funcao) in fontes_individuais.items():
        if getattr(args, arg_name, False):
            fonte_individual = (nome, funcao)
            break
    
    if fonte_individual:
        nome, funcao = fonte_individual
        print(f"🎯 Executando apenas {nome}...")
        eventos = executar_fonte(nome, funcao)
        eventos_consolidados = eventos
        sucessos = 1 if eventos else 0
        total_fontes = 1
    else:
        # Execução completa
        todos_eventos, sucessos, total_fontes = executar_scraping_completo()
        eventos_consolidados = consolidar_eventos_globais(*[todos_eventos])
    
    if eventos_consolidados:
        eventos_salvos = salvar_eventos(eventos_consolidados)
        tempo_total = (datetime.now() - start_time).total_seconds()
        
        exibir_relatorio_final(eventos_consolidados, sucessos, total_fontes, tempo_total)
        print(f"💾 {eventos_salvos} novos eventos salvos")
        print(f"📁 {os.path.abspath('data/corridas.csv')}")
    else:
        print("💀 Nenhum evento coletado")

if __name__ == "__main__":
    main()