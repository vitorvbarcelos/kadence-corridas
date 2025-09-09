import time
import hashlib
import re
from datetime import datetime
from playwright.sync_api import Page, sync_playwright, TimeoutError

def gerar_hash_evento(titulo, data, local):
    """Gera hash único para evitar duplicatas"""
    conteudo = f"{titulo.lower().strip()}{data}{local.lower().strip()}"
    return hashlib.md5(conteudo.encode()).hexdigest()[:8]

def limpar_texto(texto):
    """Remove caracteres especiais e normaliza texto"""
    if not texto:
        return ""
    # Remove vírgulas, quebras de linha, espaços extras
    texto = re.sub(r'\s+', ' ', texto.strip())
    texto = texto.replace(',', ' ')  # Remove vírgulas para não quebrar CSV
    return texto

def extrair_categoria_especifica(page, categoria_nome, url):
    """Extrai eventos de uma categoria específica"""
    eventos = []
    
    try:
        print(f"🔍 Processando categoria: {categoria_nome}")
        page.goto(url, timeout=60000)
        
        # Aguarda os primeiros cards carregarem
        try:
            page.wait_for_selector(".titulo-card-evento", timeout=15000)
            cards_iniciais = len(page.query_selector_all(".card-evento"))
            print(f"   📦 {cards_iniciais} cards iniciais")
        except TimeoutError:
            print(f"   ⚠️ {categoria_nome}: Cards não carregaram")
            return eventos
        
        # Sistema de cliques no "Mostrar Mais"
        ultimo_total = 0
        tentativas_sem_novos = 0
        max_tentativas_sem_novos = 5
        
        while tentativas_sem_novos < max_tentativas_sem_novos:
            cards = page.query_selector_all(".card-evento")
            total_atual = len(cards)
            
            if total_atual > ultimo_total:
                ultimo_total = total_atual
                tentativas_sem_novos = 0
                
                try:
                    botao_mais = page.wait_for_selector(".carregar-mais", timeout=3000)
                    if botao_mais and botao_mais.is_visible() and not botao_mais.is_disabled():
                        botao_mais.click()
                        time.sleep(2)  # Aguarda carregar
                    else:
                        print(f"   🚫 {categoria_nome}: Botão não disponível")
                        break
                except:
                    print(f"   🏁 {categoria_nome}: Fim dos eventos")
                    break
            else:
                tentativas_sem_novos += 1
                if tentativas_sem_novos <= 2:
                    time.sleep(1)
        
        # Coleta dos dados
        cards = page.query_selector_all(".card-evento")
        print(f"   🔄 {categoria_nome}: Processando {len(cards)} eventos")
        
        for i, card in enumerate(cards):
            try:
                # Título
                titulo_el = card.query_selector(".titulo-card-evento")
                titulo = limpar_texto(titulo_el.inner_text()) if titulo_el else f"Evento {i+1}"
                
                # Data
                data_el = card.query_selector(".data-card-evento")
                if data_el:
                    data_raw = limpar_texto(data_el.inner_text().split('\n')[0])
                else:
                    continue
                
                # Valida data
                try:
                    data_obj = datetime.strptime(data_raw, "%d/%m/%Y")
                    if data_obj < datetime.today():
                        continue
                    data_formatada = data_raw
                except ValueError:
                    continue
                
                # Local
                local_el = card.query_selector(".local-card-evento")
                local = limpar_texto(local_el.inner_text()) if local_el else "Local não informado"
                
                # Link
                link_el = card.query_selector("a")
                link = ""
                if link_el:
                    href = link_el.get_attribute("href")
                    if href:
                        link = href if href.startswith("http") else f"https://www.ticketsports.com.br{href}"
                
                # Validações
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
                    "fonte": f"TicketSports-{categoria_nome}",
                    "data_obj": data_obj,
                    "categoria": categoria_nome
                })
            
            except Exception:
                continue
        
        print(f"   ✅ {categoria_nome}: {len(eventos)} eventos coletados")
        
    except Exception as e:
        print(f"   ❌ {categoria_nome}: Erro - {str(e)[:50]}...")
    
    return eventos

def extrair_ticket_sports(max_tentativas=3):
    """Extrai eventos de múltiplas categorias de distância"""
    
    # URLs com filtros de distância específicos
    categorias = {
        "Geral": "https://www.ticketsports.com.br/Calendario/Todos-os-organizadores/Corrida-de-rua/Todo-o-Brasil/Todas-as-cidades/0,00/0,00/false/?termo=&periodo=0&mes=&inicio=&fim=&ordenacao=3&pais=",
        "Até 4K": "https://www.ticketsports.com.br/Calendario/Todos-os-organizadores/Corrida-de-rua/Todo-o-Brasil/Todas-as-cidades/0,00/0,00/false/?termo=&periodo=0&mes=&inicio=&fim=&ordenacao=3&pais=&modalidade=11",
        "5K-10K": "https://www.ticketsports.com.br/Calendario/Todos-os-organizadores/Corrida-de-rua/Todo-o-Brasil/Todas-as-cidades/0,00/0,00/false/?termo=&periodo=0&mes=&inicio=&fim=&ordenacao=3&pais=&modalidade=12", 
        "11K-20K": "https://www.ticketsports.com.br/Calendario/Todos-os-organizadores/Corrida-de-rua/Todo-o-Brasil/Todas-as-cidades/0,00/0,00/false/?termo=&periodo=0&mes=&inicio=&fim=&ordenacao=3&pais=&modalidade=13",
        "21K": "https://www.ticketsports.com.br/Calendario/Todos-os-organizadores/Corrida-de-rua/Todo-o-Brasil/Todas-as-cidades/0,00/0,00/false/?termo=&periodo=0&mes=&inicio=&fim=&ordenacao=3&pais=&modalidade=14",
        "42K": "https://www.ticketsports.com.br/Calendario/Todos-os-organizadores/Corrida-de-rua/Todo-o-Brasil/Todas-as-cidades/0,00/0,00/false/?termo=&periodo=0&mes=&inicio=&fim=&ordenacao=3&pais=&modalidade=15"
    }
    
    todos_eventos = []
    
    for tentativa in range(max_tentativas):
        try:
            print(f"🔎 TicketSports - Tentativa {tentativa + 1}/{max_tentativas}")
            print(f"🎯 Processando {len(categorias)} categorias de distância...")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=False)
                page = browser.new_page()
                
                eventos_por_categoria = []
                
                for categoria_nome, url in categorias.items():
                    eventos_categoria = extrair_categoria_especifica(page, categoria_nome, url)
                    eventos_por_categoria.extend(eventos_categoria)
                    
                    # Pequena pausa entre categorias
                    time.sleep(1)
                
                browser.close()
                
                if eventos_por_categoria:
                    print(f"\n🔄 Removendo duplicatas entre categorias...")
                    
                    # Remove duplicatas usando hash
                    eventos_unicos = {}
                    for evento in eventos_por_categoria:
                        hash_evento = evento['hash']
                        if hash_evento not in eventos_unicos:
                            eventos_unicos[hash_evento] = evento
                    
                    todos_eventos = list(eventos_unicos.values())
                    
                    # Ordena por data
                    todos_eventos.sort(key=lambda x: x['data_obj'])
                    
                    duplicatas_removidas = len(eventos_por_categoria) - len(todos_eventos)
                    
                    print(f"📊 RESULTADO FINAL:")
                    print(f"   🔢 Eventos coletados: {len(eventos_por_categoria)}")
                    print(f"   🔄 Duplicatas removidas: {duplicatas_removidas}")
                    print(f"   ✅ Eventos únicos: {len(todos_eventos)}")
                    
                    return todos_eventos
                else:
                    print("⚠️ Nenhum evento encontrado em nenhuma categoria")
                    
        except Exception as e:
            print(f"❌ Erro geral na tentativa {tentativa + 1}: {str(e)[:80]}...")
            if tentativa == max_tentativas - 1:
                print("💀 TicketSports falhou após todas as tentativas")
            continue
    
    return todos_eventos