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

def processar_data_cronoschip(data_str):
    """Processa data do formato Cronoschip: '17/08/2025'"""
    if not data_str:
        return None, None
    
    # Remove ícones e texto extra, mantém só a data
    data_limpa = re.sub(r'^.*?(\d{2}/\d{2}/\d{4}).*$', r'\1', data_str.strip())
    
    # Padrão: "17/08/2025"
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

def processar_local_cronoschip(local_str):
    """Processa local removendo ícone de mapa"""
    if not local_str:
        return "Local não informado"
    
    # Remove ícone de mapa e limpa o texto
    local_limpo = re.sub(r'^.*?([A-ZÁÊÇ].+)$', r'\1', local_str.strip())
    return limpar_texto(local_limpo)

def aguardar_carregamento_ajax(page, max_tentativas=30):
    """Aguarda todos os eventos carregarem via AJAX"""
    print("🔄 Aguardando carregamento completo via AJAX...")
    
    tentativa = 0
    ultimo_total = 0
    tentativas_sem_mudanca = 0
    max_tentativas_sem_mudanca = 5
    
    while tentativa < max_tentativas and tentativas_sem_mudanca < max_tentativas_sem_mudanca:
        try:
            # Scroll para o final da página para garantir que tudo carregue
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Conta cards atuais
            cards_atuais = len(page.query_selector_all(".item-app"))
            
            if cards_atuais > ultimo_total:
                ultimo_total = cards_atuais
                tentativas_sem_mudanca = 0
                print(f"   📈 Tentativa {tentativa + 1}: {cards_atuais} eventos carregados")
            else:
                tentativas_sem_mudanca += 1
                print(f"   ⏳ Tentativa {tentativa + 1}: Sem novos eventos ({tentativas_sem_mudanca}/{max_tentativas_sem_mudanca})")
            
            tentativa += 1
            time.sleep(3)  # Aguarda mais AJAX
            
        except Exception as e:
            print(f"   ⚠️ Erro na tentativa {tentativa + 1}: {str(e)[:50]}...")
            break
    
    total_final = len(page.query_selector_all(".item-app"))
    print(f"🏁 Carregamento AJAX finalizado: {total_final} eventos | {tentativa} tentativas realizadas")
    return total_final

def coletar_eventos_cronoschip(page):
    """Coleta eventos de corrida do Cronoschip"""
    eventos = []
    
    try:
        # Seleciona todos os cards de evento
        cards = page.query_selector_all(".item-app")
        print(f"   📦 {len(cards)} cards encontrados para processamento")
        
        for i, card in enumerate(cards):
            try:
                # Título
                titulo_el = card.query_selector(".item-app-header h5")
                titulo = limpar_texto(titulo_el.inner_text()) if titulo_el else ""
                
                if not titulo:
                    continue
                
                # Conteúdo do card (data e local estão juntos)
                content_el = card.query_selector(".item-app-content")
                content_text = content_el.inner_text() if content_el else ""
                
                if not content_text:
                    continue
                
                # Extrai data e local do conteúdo
                linhas = content_text.split('\n')
                data_raw = ""
                local_raw = "Local não informado"
                
                for linha in linhas:
                    linha = linha.strip()
                    if "fa-calendar" in content_el.get_attribute('innerHTML') and "/" in linha:
                        # Linha com data
                        data_raw = linha
                    elif "fa-map-marker" in content_el.get_attribute('innerHTML') and " - " in linha:
                        # Linha com local
                        local_raw = linha
                
                # Processa a data
                data_obj, data_formatada = processar_data_cronoschip(data_raw)
                if not data_obj:
                    continue
                
                # Só eventos futuros
                if data_obj < datetime.now():
                    continue
                
                # Processa o local
                local = processar_local_cronoschip(local_raw)
                
                # Link
                link_el = card.query_selector("a.theme-button")
                link = ""
                if link_el:
                    href = link_el.get_attribute("href")
                    if href:
                        link = href if href.startswith("http") else f"https://cronoschip.com.br/{href}"
                
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
                    "fonte": "Cronoschip",
                    "data_obj": data_obj
                })
                
                # Mostra detalhes dos primeiros 3 eventos
                if len(eventos) <= 3:
                    print(f"   ✅ Evento {len(eventos)}: {titulo[:35]}... | {data_formatada} | {local[:25]}...")
                
            except Exception as e:
                continue
        
        print(f"   🎯 Total de eventos válidos coletados: {len(eventos)}")
                
    except Exception as e:
        print(f"   ⚠️ Erro ao coletar eventos: {str(e)[:50]}...")
    
    return eventos

def extrair_cronoschip(max_tentativas=3):
    """Extrai eventos de corrida do Cronoschip"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 Cronoschip - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # URL do calendário do Cronoschip
                url = "https://cronoschip.com.br/provas"
                
                try:
                    print("📄 Carregando Cronoschip...")
                    page.goto(url, timeout=60000)
                    
                    # Aguarda a página carregar completamente
                    time.sleep(5)
                    
                    # Aguarda o JavaScript carregar os eventos
                    try:
                        page.wait_for_selector(".item-app", timeout=20000)
                    except TimeoutError:
                        print("   ⚠️ Cards não carregaram no tempo esperado")
                        browser.close()
                        continue
                    
                    # Aguarda carregamento completo via AJAX
                    total_cards = aguardar_carregamento_ajax(page, max_tentativas=30)
                    
                    # Agora coleta todos os eventos de uma vez
                    print(f"🔄 Processando {total_cards} eventos...")
                    eventos = coletar_eventos_cronoschip(page)
                    
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
                        
                        print(f"✅ Cronoschip: {len(eventos_finais)} eventos únicos coletados")
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
                print("💀 Cronoschip falhou após todas as tentativas")
            continue
    
    return eventos