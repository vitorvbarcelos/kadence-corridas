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

def eh_evento_de_corrida_doity(titulo, tag=""):
    """Verifica se o evento é relacionado a corrida no Doity"""
    if not titulo:
        return False
    
    titulo_lower = titulo.lower()
    tag_lower = tag.lower() if tag else ""
    
    # Palavras-chave específicas do Doity
    palavras_corrida = [
        'corrida', 'maratona', 'run', 'running', 'atletismo', 
        'cooper', 'caminhada', 'trote', 'meia maratona',
        '5k', '10k', '21k', '42k', 'km', 'trail',
        'night run', 'day run', 'street run', 'rustica'
    ]
    
    # Verifica na tag primeiro (mais confiável)
    if 'corrida' in tag_lower or 'run' in tag_lower:
        return True
    
    # Verifica no título
    for palavra in palavras_corrida:
        if palavra in titulo_lower:
            return True
    
    return False

def processar_data_doity(data_str):
    """Processa datas do formato Doity: '09 AGO 2025'"""
    if not data_str:
        return None, None
    
    # Mapeia meses em português (abreviado)
    meses = {
        'jan': '01', 'fev': '02', 'mar': '03', 'abr': '04',
        'mai': '05', 'jun': '06', 'jul': '07', 'ago': '08',
        'set': '09', 'out': '10', 'nov': '11', 'dez': '12'
    }
    
    # Remove espaços extras e converte para minúsculo
    data_limpa = re.sub(r'\s+', ' ', data_str.strip().lower())
    
    # Padrão: "09 ago 2025"
    padrao = r'(\d{1,2})\s+([a-z]{3})\s+(\d{4})'
    match = re.search(padrao, data_limpa)
    
    if match:
        dia = match.group(1).zfill(2)
        mes_texto = match.group(2)
        ano = match.group(3)
        
        mes_num = meses.get(mes_texto, '01')
        data_str_formatada = f"{dia}/{mes_num}/{ano}"
        
        try:
            data_obj = datetime.strptime(data_str_formatada, '%d/%m/%Y')
            return data_obj, data_str_formatada
        except ValueError:
            pass
    
    return None, data_str

def navegar_paginas_doity(page, max_paginas=20):
    """Navega pelas páginas do Doity usando botão 'PRÓXIMO'"""
    todos_eventos = []
    pagina_atual = 1
    
    while pagina_atual <= max_paginas:
        try:
            print(f"   📄 Processando página {pagina_atual}")
            
            # Aguarda os cards carregarem
            page.wait_for_selector(".wrapper__event-card", timeout=15000)
            
            # Coleta eventos da página atual
            eventos_pagina = coletar_eventos_pagina_doity(page)
            
            if eventos_pagina:
                todos_eventos.extend(eventos_pagina)
                print(f"   ✅ Página {pagina_atual}: {len(eventos_pagina)} corridas encontradas")
            else:
                print(f"   ⚠️ Página {pagina_atual}: nenhuma corrida encontrada")
            
            # Procura pelo botão "PRÓXIMO"
            try:
                seletores_proximo = [
                    ".wrapper__pagination__navigation:has-text('PRÓXIMO')",
                    ".wrapper__pagination__navigation__text.next",
                    ".wrapper__pagination__navigation",
                    "span:has-text('PRÓXIMO')"
                ]
                
                botao_proximo = None
                for seletor in seletores_proximo:
                    try:
                        botao_proximo = page.query_selector(seletor)
                        if botao_proximo and botao_proximo.is_visible():
                            break
                    except:
                        continue
                
                if botao_proximo:
                    print(f"   👉 Indo para página {pagina_atual + 1}")
                    botao_proximo.click()
                    time.sleep(3)  # Aguarda carregar
                    pagina_atual += 1
                else:
                    print(f"   🏁 Não há mais páginas")
                    break
                    
            except Exception as e:
                print(f"   ⚠️ Erro na navegação: {str(e)[:50]}...")
                break
                
        except Exception as e:
            print(f"   ❌ Erro na página {pagina_atual}: {str(e)[:50]}...")
            break
    
    return todos_eventos

def coletar_eventos_pagina_doity(page):
    """Coleta eventos de corrida de uma página do Doity"""
    eventos = []
    
    try:
        # Seleciona todos os cards de evento
        cards = page.query_selector_all(".wrapper__event-card")
        
        for i, card in enumerate(cards):
            try:
                # Título
                titulo_el = card.query_selector(".wrapper__event-card__content__event")
                titulo = limpar_texto(titulo_el.inner_text()) if titulo_el else ""
                
                # Tag/Categoria (para filtrar corridas)
                tag_el = card.query_selector(".wrapper__event-card__content__tag p")
                tag = limpar_texto(tag_el.inner_text()) if tag_el else ""
                
                # Filtra só eventos de corrida
                if not eh_evento_de_corrida_doity(titulo, tag):
                    continue
                
                # Data
                data_el = card.query_selector(".wrapper__event-card__content__date")
                data_raw = data_el.inner_text().strip() if data_el else ""
                
                data_obj, data_formatada = processar_data_doity(data_raw)
                if not data_obj:
                    continue
                
                # Só eventos futuros
                if data_obj < datetime.now():
                    continue
                
                # Local
                local_el = card.query_selector(".wrapper__event-card__content__place")
                local = limpar_texto(local_el.inner_text()) if local_el else "Local não informado"
                
                # Link
                href = card.get_attribute("href")
                link = href if href and href.startswith("http") else f"https://doity.com.br{href}" if href else ""
                
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
                    "fonte": "Doity",
                    "data_obj": data_obj,
                    "categoria": tag  # Mantém a categoria para referência
                })
                
                # Debug das primeiras 3 corridas
                if len(eventos) <= 3:
                    print(f"   ✅ Corrida {len(eventos)}: {titulo[:35]}... | {data_formatada} | {local[:25]}...")
                
            except Exception as e:
                continue
    
    except Exception as e:
        print(f"   ⚠️ Erro ao coletar página: {str(e)[:50]}...")
    
    return eventos

def extrair_doity(max_tentativas=3):
    """Extrai eventos de corrida do Doity"""
    eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 Doity - Tentativa {tentativa + 1}/{max_tentativas}")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                
                # URL do Doity para eventos de esporte e lazer
                url = "https://doity.com.br/eventos/esporte-lazer"
                
                try:
                    print("📄 Carregando Doity...")
                    page.goto(url, timeout=60000)
                    
                    # Aguarda a página carregar completamente (Vue.js)
                    time.sleep(5)
                    
                    # Aguarda os cards aparecerem
                    page.wait_for_selector(".wrapper__event-card", timeout=20000)
                    
                    # Navega por todas as páginas
                    eventos = navegar_paginas_doity(page, max_paginas=20)
                    
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
                        
                        print(f"✅ Doity: {len(eventos_finais)} corridas únicas coletadas")
                        if duplicatas > 0:
                            print(f"🔄 {duplicatas} duplicatas internas removidas")
                        
                        return eventos_finais
                    else:
                        print("⚠️ Nenhuma corrida encontrada")
                        
                except TimeoutError:
                    print(f"❌ Timeout na tentativa {tentativa + 1}")
                    browser.close()
                    continue
                    
        except Exception as e:
            print(f"❌ Erro geral na tentativa {tentativa + 1}: {str(e)[:80]}...")
            if tentativa == max_tentativas - 1:
                print("💀 Doity falhou após todas as tentativas")
            continue
    
    return eventos