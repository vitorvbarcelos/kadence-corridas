import time
import hashlib
import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError

def gerar_hash_evento(titulo, data, local):
    """Gera hash único para evitar duplicatas"""
    conteudo = f"{titulo.lower().strip()}{data}{local.lower().strip()}"
    return hashlib.md5(conteudo.encode()).hexdigest()[:8]

def limpar_texto(texto):
    """Remove caracteres especiais e normaliza texto"""
    if not texto:
        return ""
    texto = re.sub(r'\s+', ' ', texto.strip())
    texto = texto.replace(',', ' ')  # Remove vírgulas para não quebrar CSV
    return texto

def processar_data_brasilcorrida(data_str, hora_str=""):
    """Processa data do formato BrasilCorrida: '09/08/2025' + '08:00'"""
    if not data_str:
        return None, None
    
    # Remove espaços e caracteres extras
    data_limpa = data_str.strip()
    
    # Padrão: "09/08/2025"
    padrao = r'(\d{2})/(\d{2})/(\d{4})'
    match = re.search(padrao, data_limpa)
    
    if match:
        dia, mes, ano = match.groups()
        data_str_formatada = f"{dia}/{mes}/{ano}"
        
        try:
            data_obj = datetime.strptime(data_str_formatada, '%d/%m/%Y')
            return data_obj, data_str_formatada
        except ValueError:
            pass
    
    return None, data_str

def aguardar_carregamento_angularjs(page, max_tentativas=30):
    """Aguarda AngularJS carregar completamente e todos os eventos aparecerem"""
    print("🔄 Aguardando carregamento completo do AngularJS...")
    
    tentativa = 0
    ultimo_total = 0
    tentativas_sem_mudanca = 0
    max_tentativas_sem_mudanca = 5
    
    # Aguarda primeiro carregamento
    time.sleep(8)  # AngularJS precisa de tempo inicial
    
    while tentativa < max_tentativas and tentativas_sem_mudanca < max_tentativas_sem_mudanca:
        try:
            # Scroll para o final da página para garantir que tudo carregue
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3)  # Aguarda AJAX/lazy loading
            
            # Conta cards atuais
            cards_atuais = len(page.query_selector_all(".col-md-3 .card"))
            
            if cards_atuais > ultimo_total:
                ultimo_total = cards_atuais
                tentativas_sem_mudanca = 0
                print(f"   📈 Tentativa {tentativa + 1}: {cards_atuais} eventos carregados")
            else:
                tentativas_sem_mudanca += 1
                print(f"   ⏳ Tentativa {tentativa + 1}: Sem novos eventos ({tentativas_sem_mudanca}/{max_tentativas_sem_mudanca})")
            
            tentativa += 1
            time.sleep(2)  # Aguarda mais processamento AngularJS
            
        except Exception as e:
            print(f"   ⚠️ Erro na tentativa {tentativa + 1}: {str(e)[:50]}...")
            break
    
    total_final = len(page.query_selector_all(".col-md-3 .card"))
    print(f"🏁 Carregamento AngularJS finalizado: {total_final} eventos | {tentativa} tentativas realizadas")
    return total_final

def coletar_eventos_brasilcorrida(page):
    """Coleta eventos de corrida do BrasilCorrida"""
    eventos = []
    
    try:
        # Seleciona todos os cards de evento
        cards = page.query_selector_all(".col-md-3 .card")
        print(f"   📦 {len(cards)} cards encontrados para processamento")
        
        for i, card in enumerate(cards):
            try:
                # Título - no h6 dentro do card-body
                titulo_el = card.query_selector(".card-body h6.text-secondary")
                titulo = limpar_texto(titulo_el.inner_text()) if titulo_el else ""
                
                if not titulo:
                    continue
                
                # Data e hora - estão em divs separadas
                data_el = card.query_selector(".col-sm-6 h6")  # Data: 09/08/2025
                hora_el = card.query_selector(".col-sm-4 h6")  # Hora: 08:00
                
                data_raw = limpar_texto(data_el.inner_text()) if data_el else ""
                hora_raw = limpar_texto(hora_el.inner_text()) if hora_el else ""
                
                # Processa a data
                data_obj, data_formatada = processar_data_brasilcorrida(data_raw, hora_raw)
                if not data_obj:
                    continue
                
                # Só eventos futuros
                if data_obj < datetime.now():
                    continue
                
                # Local - CORREÇÃO: pega o campo correto do ícone de localização
                local = "Local não informado"
                
                # Busca a div que contém o ícone fa-map-marker
                local_row = card.query_selector("div.row:has(i.fa-map-marker)")
                if local_row:
                    # Pega o texto da coluna ao lado do ícone
                    local_el = local_row.query_selector(".col-sm-11 h6")
                    if local_el:
                        local_raw = limpar_texto(local_el.inner_text())
                        if local_raw and len(local_raw) > 2:
                            local = local_raw
                
                # Modalidade - badge badge-secondary
                modalidade_els = card.query_selector_all(".badge.badge-secondary")
                modalidades = []
                for mod_el in modalidade_els:
                    mod_text = limpar_texto(mod_el.inner_text())
                    if mod_text:
                        modalidades.append(mod_text)
                
                modalidade = ", ".join(modalidades) if modalidades else "Corrida de Rua"
                
                # Link - extrai do href do título
                link_el = card.query_selector(".card-body a[href*='#/evento/']")
                link = ""
                if link_el:
                    href = link_el.get_attribute("href")
                    if href:
                        # Converte de hash route para URL completa
                        slug = href.replace("#/evento/", "")
                        link = f"https://brasilcorrida.com.br/#/evento/{slug}"
                
                # Validações básicas
                if len(titulo.strip()) < 3:
                    continue
                
                # Hash para deduplicação
                evento_hash = gerar_hash_evento(titulo, data_formatada, local)
                
                eventos.append({
                    "titulo": titulo,
                    "data": data_formatada,
                    "local": local,
                    "link": link,
                    "hash": evento_hash,
                    "fonte": "BrasilCorrida",
                    "data_obj": data_obj,
                    "modalidade": modalidade,
                    "hora": hora_raw
                })
                
                # Mostra detalhes dos primeiros 3 eventos
                if len(eventos) <= 3:
                    print(f"   ✅ Evento {len(eventos)}: {titulo[:35]}... | {data_formatada} {hora_raw} | {local[:25]}...")
                
            except Exception as e:
                continue
        
        print(f"   🎯 Total de eventos válidos coletados: {len(eventos)}")
                
    except Exception as e:
        print(f"   ⚠️ Erro ao coletar eventos: {str(e)[:50]}...")
    
    return eventos

def extrair_brasilcorrida(max_tentativas=3):
    """Extrai eventos de corrida do BrasilCorrida"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 BrasilCorrida - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # URL do calendário do BrasilCorrida
                url = "https://brasilcorrida.com.br/#/calendario"
                
                try:
                    print("📄 Carregando BrasilCorrida...")
                    page.goto(url, timeout=60000)
                    
                    # Aguarda AngularJS carregar completamente
                    try:
                        page.wait_for_selector(".col-md-3 .card", timeout=20000)
                    except TimeoutError:
                        print("   ⚠️ Cards não carregaram no tempo esperado")
                        browser.close()
                        continue
                    
                    # Aguarda carregamento completo do AngularJS e lazy loading
                    total_cards = aguardar_carregamento_angularjs(page, max_tentativas=30)
                    
                    # Agora coleta todos os eventos de uma vez
                    print(f"🔄 Processando {total_cards} eventos...")
                    eventos = coletar_eventos_brasilcorrida(page)
                    
                    browser.close()
                    
                    if eventos:
                        # Remove duplicatas internas
                        eventos_unicos = {}
                        for evento in eventos:
                            hash_evento = evento['hash']
                            if hash_evento not in eventos_unicos:
                                eventos_unicos[hash_evento] = evento
                        
                        eventos_finais = list(eventos_unicos.values())
                        eventos_finais.sort(key=lambda x: x['data_obj'])
                        
                        duplicatas = len(eventos) - len(eventos_finais)
                        
                        print(f"✅ BrasilCorrida: {len(eventos_finais)} eventos únicos coletados")
                        if duplicatas > 0:
                            print(f"🔄 {duplicatas} duplicatas internas removidas")
                        
                        return eventos_finais
                    else:
                        print("⚠️ Nenhum evento encontrado")
                        
                except TimeoutError:
                    print(f"❌ Timeout na tentativa {tentativa + 1}")
                    browser.close()
                    continue
                    
        except Exception as e:
            print(f"❌ Erro geral na tentativa {tentativa + 1}: {str(e)[:80]}...")
            if tentativa == max_tentativas - 1:
                print("💀 BrasilCorrida falhou após todas as tentativas")
            continue
    
    return eventos