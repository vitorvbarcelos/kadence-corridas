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

def processar_data_sympla(data_str):
    """Processa diferentes formatos de data do Sympla"""
    if not data_str:
        return None, None
    
    # Remove textos extras e normaliza
    data_limpa = re.sub(r'^[A-Za-z]+,\s*', '', data_str)  # Remove "Domingo, "
    data_limpa = re.sub(r'\s+às.*$', '', data_limpa)      # Remove horário " às 06:00"
    
    # Mapeia meses em português
    meses = {
        'Jan': '01', 'Fev': '02', 'Mar': '03', 'Abr': '04',
        'Mai': '05', 'Jun': '06', 'Jul': '07', 'Ago': '08', 
        'Set': '09', 'Out': '10', 'Nov': '11', 'Dez': '12'
    }
    
    # Padrão: "05 de Out" -> "05/10/2025"
    padrao = r'(\d{1,2})\s+de\s+([A-Za-z]{3})'
    match = re.search(padrao, data_limpa)
    
    if match:
        dia = match.group(1).zfill(2)
        mes_texto = match.group(2)
        mes_num = meses.get(mes_texto, '01')
        
        # Assume ano atual ou próximo
        ano_atual = datetime.now().year
        data_str_formatada = f"{dia}/{mes_num}/{ano_atual}"
        
        try:
            data_obj = datetime.strptime(data_str_formatada, '%d/%m/%Y')
            # Se a data já passou, assume ano seguinte
            if data_obj < datetime.now():
                data_obj = datetime.strptime(f"{dia}/{mes_num}/{ano_atual + 1}", '%d/%m/%Y')
                data_str_formatada = f"{dia}/{mes_num}/{ano_atual + 1}"
            
            return data_obj, data_str_formatada
        except ValueError:
            pass
    
    return None, data_str

def navegar_paginas_sympla(page, max_paginas=17):
    """Navega pelas páginas do Sympla coletando eventos"""
    todos_eventos = []
    
    pagina_atual = 1
    
    while pagina_atual <= max_paginas:
        try:
            print(f"   📄 Processando página {pagina_atual}")
            
            # Aguarda cards carregarem
            page.wait_for_selector(".sympla-card", timeout=15000)
            
            # Coleta eventos da página atual
            cards = page.query_selector_all(".sympla-card")
            eventos_pagina = []
            
            for i, card in enumerate(cards):
                try:
                    # Título
                    titulo_el = card.query_selector("h3")
                    titulo = limpar_texto(titulo_el.inner_text()) if titulo_el else f"Evento {i+1}"
                    
                    # Local  
                    local_el = card.query_selector("p.pn67h1c")
                    local = limpar_texto(local_el.inner_text()) if local_el else "Local não informado"
                    
                    # Data
                    data_el = card.query_selector(".qtfy415")
                    data_raw = data_el.inner_text() if data_el else ""
                    
                    data_obj, data_formatada = processar_data_sympla(data_raw)
                    if not data_obj:
                        continue  # Pula eventos com data inválida
                    
                    # Link
                    href = card.get_attribute("href")
                    link = href if href and href.startswith("http") else f"https://www.sympla.com.br{href}" if href else ""
                    
                    # Validações básicas
                    if len(titulo.strip()) < 3:
                        continue
                    
                    # Hash para deduplicação
                    evento_hash = gerar_hash_evento(titulo, data_formatada, local)
                    
                    eventos_pagina.append({
                        "titulo": titulo,
                        "data": data_formatada, 
                        "local": local,
                        "link": link,
                        "hash": evento_hash,
                        "fonte": "Sympla",
                        "data_obj": data_obj
                    })
                    
                except Exception as e:
                    continue
            
            todos_eventos.extend(eventos_pagina)
            print(f"   ✅ Página {pagina_atual}: {len(eventos_pagina)} eventos coletados")
            
            # Tenta ir para próxima página
            try:
                # Seletores específicos baseados no HTML real
                seletores_proximo = [
                    "button:has-text('Próximo')",
                    "button .swraze2:has-text('Próximo')",
                    "button[class*='1p3nw00']:has-text('Próximo')",
                    "button:has(.swraze2)",
                    "a[aria-label='Próximo']",
                    "[data-testid='next-page']"
                ]
                
                botao_proximo = None
                for seletor in seletores_proximo:
                    try:
                        botao_proximo = page.query_selector(seletor)
                        if botao_proximo and botao_proximo.is_visible() and not botao_proximo.is_disabled():
                            print(f"   🔍 Botão encontrado: {seletor}")
                            break
                    except:
                        continue
                
                if botao_proximo:
                    print(f"   👉 Clicando para ir à página {pagina_atual + 1}")
                    botao_proximo.click()
                    time.sleep(4)  # Aguarda carregar
                    pagina_atual += 1
                else:
                    print(f"   🔍 DEBUG: Buscando botão por texto...")
                    # Fallback: busca todos os botões
                    todos_botoes = page.query_selector_all("button")
                    for botao in todos_botoes:
                        try:
                            texto = botao.inner_text().strip()
                            if "Próximo" in texto and botao.is_visible() and not botao.is_disabled():
                                print(f"   🎯 Botão encontrado por texto: '{texto}'")
                                botao.click()
                                time.sleep(4)
                                pagina_atual += 1
                                break
                        except:
                            continue
                    else:
                        print(f"   🏁 Nenhum botão 'Próximo' ativo encontrado - fim das páginas")
                        break
                    
            except Exception as e:
                print(f"   ⚠️ Erro na navegação: {str(e)[:50]}...")
                break
                
        except Exception as e:
            print(f"   ❌ Erro na página {pagina_atual}: {str(e)[:50]}...")
            break
    
    return todos_eventos

def extrair_sympla(max_tentativas=3):
    """Extrai eventos de corrida do Sympla"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 Sympla - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # URL do Sympla para eventos de corrida
                url = "https://www.sympla.com.br/eventos/esportivo?c=corrida-e-competicoes&ordem=month_trending_score"
                
                try:
                    print("📄 Carregando Sympla...")
                    page.goto(url, timeout=60000)
                    
                    # Verifica se carregou
                    page.wait_for_selector(".sympla-card", timeout=20000)
                    
                    # Navega por todas as páginas
                    eventos = navegar_paginas_sympla(page, max_paginas=17)
                    
                    browser.close()
                    
                    if eventos:
                        # Remove duplicatas
                        eventos_unicos = {}
                        for evento in eventos:
                            hash_evento = evento['hash']
                            if hash_evento not in eventos_unicos:
                                eventos_unicos[hash_evento] = evento
                        
                        eventos_finais = list(eventos_unicos.values())
                        eventos_finais.sort(key=lambda x: x['data_obj'])
                        
                        duplicatas = len(eventos) - len(eventos_finais)
                        
                        print(f"✅ Sympla: {len(eventos_finais)} eventos únicos coletados")
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
                print("💀 Sympla falhou após todas as tentativas")
            continue
    
    return eventos
