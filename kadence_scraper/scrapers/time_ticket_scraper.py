import hashlib
import re
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError
from utils import formatar_data

def gerar_hash_evento(titulo, data, local):
    """Gera hash único para evitar duplicatas"""
    conteudo = f"{titulo.lower().strip()}{data}{local.lower().strip()}"
    return hashlib.md5(conteudo.encode()).hexdigest()[:8]

def extrair_link_evento(card):
    """Tenta extrair o link específico do evento"""
    try:
        # Procura por links dentro do card
        link_element = card.query_selector("a")
        if link_element:
            href = link_element.get_attribute("href")
            if href and href.startswith("/"):
                return f"https://timeticket.com.br{href}"
            elif href and href.startswith("http"):
                return href
    except:
        pass
    return "https://timeticket.com.br/"

def limpar_texto(texto):
    """Remove caracteres especiais e normaliza texto"""
    if not texto:
        return ""
    # Remove quebras de linha, espaços extras
    texto = re.sub(r'\s+', ' ', texto.strip())
    return texto

def extrair_timeticket(max_tentativas=3):
    eventos = []
    url = "https://timeticket.com.br/"
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 TimeTicket - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                navegador = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )
                pagina = navegador.new_page()
                
                # Headers para parecer mais humano
                pagina.set_extra_http_headers({
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                })
                
                pagina.goto(url, timeout=30000, wait_until="domcontentloaded")
                
                # Aguarda os cards carregarem com timeout menor
                try:
                    pagina.wait_for_selector("div.clickable-element.bubble-element.Group", timeout=15000)
                except TimeoutError:
                    print("⚠️ Cards não carregaram, tentando scroll...")
                    pagina.mouse.wheel(0, 1000)
                    pagina.wait_for_timeout(2000)
                
                # Seleciona todos os cards
                cards = pagina.query_selector_all("div.clickable-element.bubble-element.Group")
                print(f"📦 {len(cards)} cards encontrados")
                
                if not cards:
                    navegador.close()
                    continue
                
                eventos_processados = set()
                
                for i, card in enumerate(cards):
                    try:
                        # Título
                        titulo_element = card.query_selector("div.bubble-element.Text.baTaTaRaG")
                        titulo = limpar_texto(titulo_element.inner_text()) if titulo_element else f"Evento {i+1}"
                        
                        # Data
                        data_element = card.query_selector("div.bubble-element.Text.baTapaH")
                        if data_element:
                            data_raw = limpar_texto(data_element.inner_text())
                            # Remove prefixos de dia da semana
                            data_raw = re.sub(r'^(Dom|Seg|Ter|Qua|Qui|Sex|Sáb|Sab)\s+', '', data_raw)
                            data_formatada = formatar_data(data_raw)
                        else:
                            data_formatada = "Data não encontrada"
                        
                        # Local
                        local_element = card.query_selector("div.bubble-element.Text.baTaov")
                        local = limpar_texto(local_element.inner_text()) if local_element else "Local não informado"
                        
                        # Link específico do evento
                        link = extrair_link_evento(card)
                        
                        # Gera hash para evitar duplicatas
                        evento_hash = gerar_hash_evento(titulo, data_formatada, local)
                        
                        if evento_hash not in eventos_processados:
                            eventos_processados.add(evento_hash)
                            eventos.append({
                                "titulo": titulo,
                                "data": data_formatada,
                                "local": local,
                                "link": link,
                                "hash": evento_hash,
                                "fonte": "TimeTicket"
                            })
                    
                    except Exception as e:
                        print(f"⚠️ Erro no card {i+1}: {str(e)[:50]}...")
                        continue
                
                navegador.close()
                
                if eventos:
                    print(f"✅ TimeTicket: {len(eventos)} eventos únicos coletados")
                    return eventos
                else:
                    print("⚠️ Nenhum evento válido encontrado")
                    
        except Exception as e:
            print(f"❌ Erro na tentativa {tentativa + 1}: {str(e)[:100]}...")
            if tentativa == max_tentativas - 1:
                print("💀 TimeTicket falhou após todas as tentativas")
            continue
    
    return eventos