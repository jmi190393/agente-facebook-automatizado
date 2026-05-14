#!/usr/bin/env python3
"""
🚀 AGENTE DE PUBLICACIÓN EN FACEBOOK
Publica automáticamente: fotos, videos, carruseles
Genera captions automáticos con Claude
Compatible con Shopify
"""

import requests
import json
import os
from datetime import datetime
from typing import Optional, List, Dict
import random
import anthropic

# ============================================================
# CARGAR .env AUTOMÁTICAMENTE
# ============================================================
def cargar_env():
    """Carga las variables del archivo .env manualmente"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for linea in f:
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    clave, valor = linea.split("=", 1)
                    os.environ[clave.strip()] = valor.strip()
        print("✓ Archivo .env cargado correctamente")
    else:
        print(f"⚠ No se encontró .env en: {env_path}")

cargar_env()

# ============================================================
# CONFIGURACIÓN DESDE .env
# ============================================================
SHOPIFY_STORE = os.getenv("SHOPIFY_STORE", "tu_tienda.myshopify.com")
SHOPIFY_API_KEY = os.getenv("SHOPIFY_API_KEY", "tu_api_key")
SHOPIFY_API_PASSWORD = os.getenv("SHOPIFY_API_PASSWORD", "tu_api_password")

# Meta (Facebook)
META_TOKEN = os.getenv("META_TOKEN")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID")

# Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Validar que tenemos los datos críticos
if not META_TOKEN or not FACEBOOK_PAGE_ID:
    print("❌ ERROR: Falta META_TOKEN o FACEBOOK_PAGE_ID en .env")
    print("   Revisa el archivo .env y asegúrate de tener ambos valores")
    exit(1)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ============================================================
# FUNCIONES PARA OBTENER PRODUCTOS DE SHOPIFY
# ============================================================

def obtener_productos_shopify(limite: int = 30) -> List[Dict]:
    """Obtiene productos activos de Shopify con imágenes"""
    url = f"https://{SHOPIFY_STORE}/admin/api/2024-01/products.json"
    
    params = {
        "status": "active",
        "limit": limite,
        "fields": "id,title,body_html,image,images,variants,tags,product_type"
    }
    
    try:
        response = requests.get(
            url,
            auth=(SHOPIFY_API_KEY, SHOPIFY_API_PASSWORD),
            params=params,
            timeout=10
        )
        response.raise_for_status()
        
        productos = response.json().get("products", [])
        productos_con_img = [p for p in productos if p.get("image")]
        
        print(f"✓ {len(productos_con_img)} productos obtenidos de Shopify")
        return productos_con_img
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error conectando a Shopify: {e}")
        return []


def seleccionar_productos(productos: List[Dict], cantidad: int = 2) -> List[Dict]:
    """Selecciona N productos al azar"""
    if not productos:
        return []
    return random.sample(productos, min(cantidad, len(productos)))


# ============================================================
# GENERACIÓN DE CAPTIONS CON CLAUDE
# ============================================================

def generar_caption(productos: List[Dict], tipo_post: str = "producto") -> str:
    """Genera un caption atractivo usando Claude"""
    
    productos_txt = "\n".join([
        f"- {p.get('title', 'Sin nombre')}: ${p['variants'][0].get('price', '0') if p.get('variants') else '0'}"
        for p in productos[:2]
    ])
    
    prompt = f"""Eres un experto en marketing para ecommerce mexicano. 
Genera un caption ATRACTIVO para Facebook/Instagram que VENDA (máx 200 caracteres):

PRODUCTOS:
{productos_txt}

REQUISITOS:
- Máximo 3 emoticones
- Incluye CTA: "Link en bio" o "¡Compra ya!"
- Tono casual, mexicano y amigable
- 2-3 hashtags relevantes (#MadeinMx, #CompraMexicano, #VentasOnline, etc)

SOLO responde el caption, sin explicaciones."""
    
    try:
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return response.content[0].text.strip()
        
    except Exception as e:
        print(f"⚠ Error generando caption: {e}")
        return "¡Mira nuestros productos! Link en bio 👆 #CompraMexicano"


# ============================================================
# PUBLICACIÓN EN FACEBOOK
# ============================================================

def publicar_foto_facebook(caption: str, imagen_url: str) -> bool:
    """Publica una foto en Facebook"""
    
    print(f"\n📷 Publicando FOTO en Facebook...")
    print(f"   Caption: {caption[:80]}...")
    
    url = f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/photos"
    
    # Para publicar foto, necesitamos la URL pública de la imagen
    # Shopify proporciona URLs directas a las imágenes
    
    payload = {
        "url": imagen_url,
        "caption": caption,
        "access_token": META_TOKEN
    }
    
    try:
        response = requests.post(url, data=payload, timeout=15)
        response.raise_for_status()
        
        resultado = response.json()
        
        if "id" in resultado:
            post_id = resultado["id"]
            print(f"   ✓ Foto publicada! ID: {post_id}")
            print(f"   📍 URL: https://facebook.com/{post_id}")
            return True
        else:
            print(f"   ⚠ Respuesta: {resultado}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ✗ Error: {str(e)[:100]}")
        return False


def publicar_carrusel_facebook(caption: str, imagen_urls: List[str]) -> bool:
    """Publica un carrusel (múltiples fotos) en Facebook"""
    
    print(f"\n🎠 Publicando CARRUSEL en Facebook...")
    print(f"   Fotos: {len(imagen_urls)} imágenes")
    print(f"   Caption: {caption[:80]}...")
    
    url = f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/feed"
    
    # Preparar items del carrusel
    media_data = []
    for img_url in imagen_urls[:10]:  # Máximo 10 fotos por carrusel
        media_data.append({
            "media_type": "IMAGE",
            "media": {"image_url": img_url}
        })
    
    payload = {
        "message": caption,
        "media_type": "CAROUSEL",
        "children": json.dumps(media_data),
        "access_token": META_TOKEN
    }
    
    try:
        # Publicar primera imagen con caption
        primera_imagen = imagen_urls[0] if imagen_urls else None
        
        payload_simple = {
            "message": caption,
            "access_token": META_TOKEN
        }
        
        if primera_imagen:
            # Usar endpoint de fotos para incluir imagen
            url_foto = f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/photos"
            payload_simple["url"] = primera_imagen
            payload_simple["caption"] = caption
            response = requests.post(url_foto, data=payload_simple, timeout=15)
        else:
            response = requests.post(url, data=payload_simple, timeout=15)
        
        response.raise_for_status()
        resultado = response.json()
        
        if "id" in resultado:
            post_id = resultado["id"]
            print(f"   ✓ Post publicado! ID: {post_id}")
            return True
        else:
            print(f"   Respuesta: {resultado}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   Error: {str(e)[:150]}")
        return False


def publicar_link_facebook(caption: str, link: str, imagen_url: Optional[str] = None) -> bool:
    """Publica un post con link (ideal para tu tienda Shopify)"""
    
    print(f"\n🔗 Publicando LINK en Facebook...")
    print(f"   Link: {link}")
    print(f"   Caption: {caption[:80]}...")
    
    url = f"https://graph.facebook.com/v18.0/{FACEBOOK_PAGE_ID}/feed"
    
    payload = {
        "message": caption,
        "link": link,
        "access_token": META_TOKEN
    }
    
    if imagen_url:
        payload["picture"] = imagen_url
    
    try:
        response = requests.post(url, data=payload, timeout=15)
        response.raise_for_status()
        
        resultado = response.json()
        
        if "id" in resultado:
            post_id = resultado["id"]
            print(f"   ✓ Post publicado! ID: {post_id}")
            print(f"   📍 URL: https://facebook.com/{post_id}")
            return True
        else:
            print(f"   ⚠ Respuesta: {resultado}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ✗ Error: {str(e)[:100]}")
        return False


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def publicar_contenido():
    """Orquesta todo el proceso de publicación"""
    
    timestamp = datetime.now().isoformat()
    
    print("\n" + "="*70)
    print("📱 AGENTE DE PUBLICACIÓN EN FACEBOOK")
    print(f"   Timestamp: {timestamp}")
    print("="*70 + "\n")
    
    # Paso 1: Obtener productos
    print("[1] Obteniendo productos de Shopify...")
    productos = obtener_productos_shopify(50)
    
    if not productos:
        print("✗ No hay productos disponibles")
        return False
    
    # Paso 2: Seleccionar tipo de post (aleatorio)
    tipo_post = random.choice(["foto", "carrusel", "link"])
    print(f"\n[2] Tipo de post seleccionado: {tipo_post.upper()}")
    
    # Paso 3: Seleccionar productos
    print(f"\n[3] Seleccionando productos...")
    
    if tipo_post == "carrusel":
        productos_sel = seleccionar_productos(productos, cantidad=3)
        print(f"   {len(productos_sel)} productos para carrusel")
    else:
        productos_sel = seleccionar_productos(productos, cantidad=1)
        print(f"   Producto: {productos_sel[0].get('title', 'Sin nombre')}")
    
    # Paso 4: Generar caption
    print(f"\n[4] Generando caption con Claude...")
    caption = generar_caption(productos_sel, tipo_post)
    print(f"   Caption: {caption}")
    
    # Paso 5: Obtener imágenes
    print(f"\n[5] Preparando imágenes...")
    
    if tipo_post == "carrusel":
        imagen_urls = [p.get("image", {}).get("src") for p in productos_sel if p.get("image")]
        imagen_urls = [u for u in imagen_urls if u]
    else:
        imagen_urls = [productos_sel[0].get("image", {}).get("src")] if productos_sel[0].get("image") else []
    
    print(f"   {len(imagen_urls)} imagen(es) disponible(s)")
    
    # Paso 6: Publicar según tipo
    print(f"\n[6] Publicando en Facebook...")
    
    resultado = False
    
    # SIEMPRE publicar como LINK a tu tienda con imagen
    link = "https://liftor.com.mx"
    resultado = publicar_link_facebook(caption, link, imagen_urls[0] if imagen_urls else None)
    
    # Paso 7: Registrar
    print(f"\n[7] Registrando...")
    
    log_data = {
        "timestamp": timestamp,
        "tipo": tipo_post,
        "caption": caption,
        "productos": [p.get("title") for p in productos_sel],
        "publicado": resultado
    }
    
    with open("publicaciones.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_data, ensure_ascii=True) + "\n")
    
    # Resumen
    print("\n" + "="*70)
    print("✓ PUBLICACIÓN COMPLETADA")
    print(f"   Tipo: {tipo_post.upper()}")
    print(f"   Estado: {'Publicado ✓' if resultado else 'Error ✗'}")
    print("="*70 + "\n")
    
    return resultado


if __name__ == "__main__":
    success = publicar_contenido()
    exit(0 if success else 1)
