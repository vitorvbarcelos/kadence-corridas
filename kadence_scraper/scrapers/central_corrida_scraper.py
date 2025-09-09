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

def processar_data_central(data_str):
    """Processa diferentes formatos de data da Central da Corrida"""
    if not data_str:
        return None, None
    
    # Remove texto extra e normaliza - formato: "10/08/2025 - 06:30"
    data_limpa = data_str.split(' - ')[0].strip()  # Pega só a parte da data
    
    # Padrão: "10/08/2025"
    try:
        data_obj = datetime.strptime(data_limpa, '%d/%m/%Y')
        return data_obj, data_limpa
    except ValueError:
        pass
    
    return None, data_str

def fazer_scroll_infinito(page, max_scrolls=50):
    """Faz scroll até carregar todos os eventos disponíveis"""
    print("🔄 Fazendo scroll para carregar todos os eventos...")
    
    scroll_realizados = 0
    eventos_anteriores = 0
    tentativas_sem_novos = 0
    max_tentativas_sem_novos = 5
    
    while scroll_realizados < max_scrolls and tentativas_sem_novos < max_tentativas_sem_novos:
        try:
            # Conta eventos atuais
            cards_atuais = len(page.query_selector_all(".clickable-element.bubble-element.Group"))
            
            # Scroll para baixo
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3)  # Aguarda carregar novos eventos
            
            # Conta eventos após scroll
            cards_novos = len(page.query_selector_all(".clickable-element.bubble-element.Group"))
            
            if cards_novos > eventos_anteriores:
                eventos_anteriores = cards_novos
                tentativas_sem_novos = 0
                print(f"   📈 Scroll {scroll_realizados + 1}: {cards_novos} eventos carregados")
            else:
                tentativas_sem_novos += 1
                print(f"   ⏳ Scroll {scroll_realizados + 1}: Sem novos eventos ({tentativas_sem_novos}/{max_tentativas_sem_novos})")
            
            scroll_realizados += 1
            
        except Exception as e:
            print(f"   ⚠️ Erro no scroll {scroll_realizados + 1}: {str(e)[:50]}...")
            break
    
    total_final = len(page.query_selector_all(".clickable-element.bubble-element.Group"))
    print(f"🏁 Scroll finalizado: {total_final} eventos carregados | {scroll_realizados} scrolls realizados")
    return total_final

def coletar_eventos_central(page):
    """Coleta eventos da Central da Corrida"""
    eventos = []
    
    try:
        # Seleciona todos os cards de evento
        cards = page.query_selector_all(".clickable-element.bubble-element.Group")
        print(f"   📦 {len(cards)} cards encontrados para processamento")
        
        for i, card in enumerate(cards):
            try:
                # Busca todos os elementos de texto do card
                text_elements = card.query_selector_all(".bubble-element.Text")
                
                if len(text_elements) < 3:  # Precisa ter pelo menos título, data e local
                    continue
                
                # Título (primeiro elemento de texto maior)
                titulo = ""
                data_raw = ""
                local = "Local não informado"
                
                for j, text_el in enumerate(text_elements):
                    try:
                        texto = limpar_texto(text_el.inner_text())
                        
                        if not texto:
                            continue
                        
                        # Primeira análise: procura por padrões
                        if "/" in texto and "-" in texto:  # Padrão de data: "10/08/2025 - 06:30"
                            data_raw = texto
                        elif len(texto.split()) >= 2 and not "/" in texto and not "-" in texto and j == 0:
                            # Primeiro texto longo sem data = título
                            titulo = texto
                        elif "SE" in texto or "SP" in texto or "RJ" in texto or "MG" in texto:
                            # Contém sigla de estado = local
                            local = texto
                        elif len(texto) > 10 and not titulo and not "/" in texto:
                            # Texto longo sem data e sem título ainda = título
                            titulo = texto
                        elif len(texto) < 30 and not local.endswith(("SE", "SP", "RJ", "MG", "RS", "SC", "PR", "BA", "GO", "DF")):
                            # Texto curto sem estado identificado = possível local
                            if "não informado" in local:
                                local = texto
                    
                    except Exception:
                        continue
                
                # Se não conseguiu identificar título, pega o primeiro texto
                if not titulo and text_elements:
                    titulo = limpar_texto(text_elements[0].inner_text())
                
                # Processa a data
                data_obj, data_formatada = processar_data_central(data_raw)
                if not data_obj:
                    continue
                
                # Só eventos futuros
                if data_obj < datetime.now():
                    continue
                
                # Validações básicas
                if len(titulo.strip()) < 3:
                    continue
                
                # Link - tenta pegar do card clicável
                link = "https://centraldacorrida.com.br/"  # Link base por enquanto
                
                # Hash para deduplicação
                evento_hash = gerar_hash_evento(titulo, data_formatada, local)
                
                eventos.append({
                    "titulo": titulo,
                    "data": data_formatada,
                    "local": local,
                    "link": link,
                    "hash": evento_hash,
                    "fonte": "CentralDaCorrida",
                    "data_obj": data_obj
                })
                
                # Debug das primeiras 3 corridas
                if len(eventos) <= 3:
                    print(f"   ✅ Evento {len(eventos)}: {titulo[:40]}... | {data_formatada} | {local[:30]}...")
                
            except Exception as e:
                continue
        
        print(f"   🎯 Total de eventos válidos coletados: {len(eventos)}")
                
    except Exception as e:
        print(f"   ⚠️ Erro ao coletar eventos: {str(e)[:50]}...")
    
    return eventos

def extrair_central_corrida(max_tentativas=3):
    """Extrai eventos da Central da Corrida"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 Central da Corrida - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Aguarda carregar
                page.route("**/*.{png,jpg,jpeg,gif,svg,webp}", lambda route: route.abort())
                
                try:
                    print("📄 Carregando Central da Corrida...")
                    page.goto("https://centraldacorrida.com.br/", timeout=60000)
                    
                    # Aguarda a página carregar (é uma SPA com Bubble.io)
                    time.sleep(8)  # Bubble.io precisa de mais tempo para carregar
                    
                    # Aguarda os cards aparecerem
                    try:
                        page.wait_for_selector(".clickable-element.bubble-element.Group", timeout=20000)
                    except TimeoutError:
                        print("   ⚠️ Cards não carregaram no tempo esperado")
                        browser.close()
                        continue
                    
                    # Faz scroll infinito para carregar todos os eventos
                    total_cards = fazer_scroll_infinito(page, max_scrolls=50)
                    
                    # Coleta todos os eventos
                    print(f"🔄 Processando {total_cards} cards em busca de eventos válidos...")
                    eventos = coletar_eventos_central(page)
                    
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
                        
                        print(f"✅ Central da Corrida: {len(eventos_finais)} eventos únicos coletados")
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
                print("💀 Central da Corrida falhou após todas as tentativas")
            continue
    
    return eventos