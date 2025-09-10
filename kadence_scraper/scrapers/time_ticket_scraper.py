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
    texto = texto.replace(',', ' ')
    return texto

def eh_evento_de_corrida(titulo, descricao=""):
    """Verifica se o evento é relacionado a corrida"""
    if not titulo:
        return False
    
    texto_completo = f"{titulo.lower()} {descricao.lower()}"
    
    palavras_corrida = [
        'corrida', 'maratona', 'run', 'running', 'atletismo', 
        'cooper', 'caminhada', 'trote', 'meia maratona',
        '5k', '10k', '21k', '42k', 'km', 'trail',
        'night run', 'day run', 'street run', 'rustica',
        'travessia', 'mountain bike', 'mtb', 'bike'
    ]
    
    for palavra in palavras_corrida:
        if palavra in texto_completo:
            return True
    
    return False

def processar_data_timeticket(data_str):
    """Processa datas do TimeTicket: 'Sab - 20/09/2025'"""
    if not data_str:
        return None, None
    
    # Remove prefixos de dia da semana e limpa
    data_limpa = re.sub(r'^(Dom|Seg|Ter|Qua|Qui|Sex|Sáb|Sab)\s*-?\s*', '', data_str.strip())
    
    # Padrão: "20/09/2025"
    padrao = r'(\d{1,2})/(\d{1,2})/(\d{4})'
    match = re.search(padrao, data_limpa)
    
    if match:
        dia = match.group(1).zfill(2)
        mes = match.group(2).zfill(2)
        ano = match.group(3)
        
        data_str_formatada = f"{dia}/{mes}/{ano}"
        
        try:
            data_obj = datetime.strptime(data_str_formatada, '%d/%m/%Y')
            return data_obj, data_str_formatada
        except ValueError:
            pass
    
    return None, data_str

def scroll_ate_o_fim(page, max_scrolls=20):
    """Faz scroll até carregar todos os eventos"""
    print("📜 Fazendo scroll para carregar todos os eventos...")
    
    scrolls_realizados = 0
    scrolls_sem_novos_cards = 0
    ultimo_total_cards = 0
    
    while scrolls_realizados < max_scrolls and scrolls_sem_novos_cards < 3:
        # Conta cards antes do scroll
        cards_antes = len(page.query_selector_all(".bubble-element.group-item"))
        
        # Faz scroll
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)  # Aguarda carregar
        
        # Conta cards depois do scroll
        cards_depois = len(page.query_selector_all(".bubble-element.group-item"))
        
        scrolls_realizados += 1
        
        if cards_depois > cards_antes:
            scrolls_sem_novos_cards = 0
            print(f"   📈 Scroll {scrolls_realizados}: {cards_depois} cards total (+{cards_depois - cards_antes} novos)")
        else:
            scrolls_sem_novos_cards += 1
            print(f"   ⏳ Scroll {scrolls_realizados}: Sem novos cards ({scrolls_sem_novos_cards}/3)")
        
        ultimo_total_cards = cards_depois
    
    print(f"🏁 Scroll finalizado: {ultimo_total_cards} cards encontrados")
    return ultimo_total_cards

def coletar_eventos_timeticket(page):
    """Coleta eventos da página do TimeTicket"""
    eventos = []
    
    try:
        # Seleciona todos os cards de evento
        cards = page.query_selector_all(".bubble-element.group-item")
        print(f"🔍 Analisando {len(cards)} cards...")
        
        for i, card in enumerate(cards):
            try:
                # Título - busca pelo texto principal do evento
                titulo_elements = card.query_selector_all(".bubble-element.Text")
                titulo = ""
                descricao = ""
                
                for el in titulo_elements:
                    try:
                        texto = limpar_texto(el.inner_text())
                        if len(texto) > 10 and not titulo:  # Primeiro texto longo é o título
                            titulo = texto
                        elif len(texto) > 20 and not descricao:  # Segundo texto longo é descrição
                            descricao = texto
                    except:
                        continue
                
                if not titulo:
                    continue
                
                # Filtra apenas eventos de corrida
                if not eh_evento_de_corrida(titulo, descricao):
                    continue
                
                # Data - busca por texto que contenha data
                data_el = None
                data_raw = ""
                
                for el in titulo_elements:
                    try:
                        texto = el.inner_text().strip()
                        if re.search(r'\d{1,2}/\d{1,2}/\d{4}', texto):
                            data_raw = texto
                            break
                    except:
                        continue
                
                data_obj, data_formatada = processar_data_timeticket(data_raw)
                if not data_obj:
                    continue
                
                # Só eventos futuros
                if data_obj < datetime.now():
                    continue
                
                # Local - busca por texto que parece ser local
                local = "Local não informado"
                for el in titulo_elements:
                    try:
                        texto = limpar_texto(el.inner_text())
                        # Procura por padrões de cidade: "Cidade | Estado" ou similar
                        if re.search(r'[A-Z][a-z]+\s*\|\s*[A-Z]{2}', texto) or 'MG' in texto or 'SP' in texto:
                            local = texto
                            break
                    except:
                        continue
                
                # Link - tenta encontrar link clicável
                link = "https://timeticket.com.br/"
                try:
                    link_el = card.query_selector(".clickable-element")
                    if link_el:
                        onclick = link_el.get_attribute("onclick") or ""
                        if "navigate" in onclick:
                            # Extrai URL do JavaScript se possível
                            url_match = re.search(r'["\']([^"\']+)["\']', onclick)
                            if url_match:
                                relative_url = url_match.group(1)
                                if relative_url.startswith('/'):
                                    link = f"https://timeticket.com.br{relative_url}"
                except:
                    pass
                
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
                    "fonte": "TimeTicket",
                    "data_obj": data_obj
                })
                
                # Debug das primeiras 3 corridas
                if len(eventos) <= 3:
                    print(f"   ✅ Corrida {len(eventos)}: {titulo[:40]}... | {data_formatada} | {local[:25]}...")
                
            except Exception as e:
                continue
    
    except Exception as e:
        print(f"   ⚠️ Erro ao coletar eventos: {str(e)[:50]}...")
    
    return eventos

def extrair_timeticket(max_tentativas=3):
    """Extrai eventos de corrida do TimeTicket"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 TimeTicket - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Headers para parecer mais humano
                page.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                })
                
                url = "https://timeticket.com.br/"
                
                try:
                    print("📄 Carregando TimeTicket...")
                    page.goto(url, timeout=60000)
                    
                    # Aguarda a página carregar (Bubble é SPA)
                    time.sleep(5)
                    
                    # Aguarda os primeiros cards aparecerem
                    page.wait_for_selector(".bubble-element.group-item", timeout=20000)
                    
                    # Faz scroll para carregar todos os eventos
                    total_cards = scroll_ate_o_fim(page, max_scrolls=20)
                    
                    # Coleta os eventos
                    eventos = coletar_eventos_timeticket(page)
                    
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
                        
                        print(f"✅ TimeTicket: {len(eventos_finais)} corridas únicas coletadas")
                        if duplicatas > 0:
                            print(f"🔄 {duplicatas} duplicatas internas removidas")
                        
                        return eventos_finais
                    else:
                        print("⚠️ Nenhuma corrida encontrada")
                        
                except TimeoutError:
                    print(f"⌛ Timeout na tentativa {tentativa + 1}")
                    browser.close()
                    continue
                    
        except Exception as e:
            print(f"⌛ Erro geral na tentativa {tentativa + 1}: {str(e)[:80]}...")
            if tentativa == max_tentativas - 1:
                print("💀 TimeTicket falhou após todas as tentativas")
            continue
    
    return eventos
