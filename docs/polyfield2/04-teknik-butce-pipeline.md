# 04 — Teknik Bütçe ve Asset Pipeline

## Hedef Cihaz Matrisi

Polyfield 1'in en somut teknik borcu, düşük cihazlarda kare düşüşleri. Polyfield 2'de hedef cihazlar **önce** tanımlanır, içerik sonra ona göre üretilir.

| Profil | Referans cihaz | Çözünürlük | Hedef FPS | GPU sınıfı |
| --- | --- | --- | --- | --- |
| **Düşük** | Snapdragon 665 / Helio G85, 3 GB RAM | 0.65× ölçek | 30 kilitli | Adreno 610 sınıfı |
| **Orta** | Snapdragon 720G / Dimensity 810, 4 GB | 0.8× ölçek | 45 | Adreno 618 sınıfı |
| **Yüksek** | Snapdragon 8 Gen 1 / A14, 6 GB+ | 1.0× | 60 | — |
| **Ultra** | Snapdragon 8 Gen 3 / A17+, 8 GB+ | 1.0× | 60–120 | — |

Minimum: Android 8.0 (Polyfield 1'de 7.0 idi — 8.0'a çıkmak Vulkan ve bellek yönetimi açısından kazandırıyor), iOS 14.

## Kare Bütçesi (Düşük profil, 30 FPS = 33 ms)

| Kalem | Bütçe |
| --- | --- |
| CPU — oyun mantığı | 8 ms |
| CPU — ağ / senkronizasyon | 4 ms |
| CPU — animasyon (64 karakter) | 5 ms |
| CPU — render hazırlık | 6 ms |
| GPU — toplam | 22 ms |
| **Draw call (kare başına)** | **≤ 220** |
| **Görünür üçgen (kare başına)** | **≤ 280 000** |
| **Aktif partikül** | **≤ 400** |
| **Overdraw ortalaması** | **≤ 2.2×** |
| **Bellek (RAM)** | **≤ 1.4 GB** |
| **Doku belleği (VRAM)** | **≤ 420 MB** |

Ultra profilinde bu değerler sırasıyla 900 draw call / 1.4 M üçgen / 1200 partikül.

## Paket Boyutu Hedefi

| Kalem | Hedef |
| --- | --- |
| İlk indirme (Play Store / App Store) | ≤ 180 MB |
| İlk açılış sonrası zorunlu indirme | ≤ 250 MB |
| Toplam kurulu boyut | ≤ 700 MB |

Polyfield 1'in tek parça 257 MB APK'sı yerine **Play Asset Delivery / On-Demand Resources** kullanılır: temel oyun + Normandiya biyomu ilk indirmede, diğer biyomlar talep üzerine. Bu, düşük bant genişliğine sahip pazarlarda (Polyfield'ın kullanıcı tabanının önemli bir kısmı) dönüşümü doğrudan artırır.

## Doku Stratejisi

| Varlık türü | Çözünürlük | Format |
| --- | --- | --- |
| Palet atlası (tüm çevre) | 512×512 | ASTC 6×6 / ETC2 |
| Karakter atlası (millet başına) | 512×512 | ASTC 6×6 |
| Silah atlası | 1024×1024 (2 adet) | ASTC 6×6 |
| Araç atlası | 1024×1024 (millet başına) | ASTC 6×6 |
| VFX flipbook | 256×256 | ASTC 8×8 |
| UI atlası | 2048×2048 | ASTC 6×6 + alfa |

**Normal map, roughness map, metallic map kullanılmaz.** Bu tek karar doku belleğini ~%60 azaltır ve stil hedefiyle birebir uyumludur.

## Materyal ve Batching

- **Tek çevre materyali.** Tüm statik çevre, paylaşılan palet atlası + tek shader kullanır → agresif static batching.
- **GPU instancing** ağaç, çim, kaya, kum torbası, çit gibi tekrar eden propta zorunlu.
- **SRP Batcher / dinamik batching** karakter ve araçlarda.
- Shader varyant sayısı ≤ 40. Her yeni varyant, teknik sanat gözden geçirmesinden geçer (shader varyant patlaması, mobil yükleme süresinin bir numaralı sebebidir).

## LOD ve Culling Kuralları

| Mekanizma | Kural |
| --- | --- |
| LOD geçişleri | Ekran yüksekliği yüzdesine göre; %60 / %30 / %12 / cull |
| Occlusion culling | Kent haritalarında zorunlu, açık haritalarda mesafe culling yeterli |
| Karakter animasyon LOD | 60 m sonrası 15 Hz, 120 m sonrası 5 Hz güncelleme |
| Gölge culling | 60 m'den uzak nesneler gölge dökmez |
| Sis mesafesi | Görüş mesafesi bütçesidir; biyom sisi far-clip ile eşleşir |

## Asset Kabul Kontrol Listesi

Her asset, depoya girmeden önce bu listeden geçer. Otomatik kontrol CI'da çalışır.

- [ ] Üçgen sayısı kategorisinin bütçesi içinde
- [ ] LOD zinciri tam (LOD0–LOD2, karakterde LOD3)
- [ ] Pivot doğru konumda (çevre: sol-alt-arka; araç: zemin merkezi)
- [ ] Ölçek 1.0, rotasyon sıfırlanmış, transform "apply" edilmiş
- [ ] 1 m ızgaraya oturuyor (modüler çevre için)
- [ ] Paylaşılan atlasa UV'lenmiş, ek materyal yok
- [ ] Materyal sayısı ≤ 2
- [ ] Çarpışma (collider) ayrı ve basitleştirilmiş (≤ %10 tri)
- [ ] İsimlendirme kuralına uygun
- [ ] Siluet testi geçti (128 px, siyah dolgu, tanınabilir)
- [ ] Ters normal / kopuk vertex yok
- [ ] Düşük profil test sahnesinde 100 kopya ile 30 FPS altına düşürmüyor

## İsimlendirme Kuralı

```
<tip>_<kategori>_<isim>_<varyant>_<lod>

sm_env_wall_brick_02_lod0      # static mesh
sk_chr_us_infantry_body        # skeletal mesh
sm_wpn_thompson_m1a1_lod0
sm_veh_sherman_m4a3_lod1
tex_env_palette_master
mat_env_shared
vfx_exp_grenade_01
anim_chr_run_fwd
sfx_wpn_mg42_close
ui_ico_weapon_stengun
```

Biyom son eki gerektiğinde: `_nor` (Normandiya), `_win` (kış), `_des` (çöl), `_pac` (Pasifik), `_urb` (kent), `_alp` (Alp).

## Klasör Yapısı

```
Assets/
  Art/
    Characters/  <millet>/  {Meshes, Materials, Textures, Anims}
    Weapons/     <millet>/
    Vehicles/    <millet>/
    Environment/
      Modular/   {Walls, Floors, Roofs, Doors, Ruins}
      Nature/    <biyom>/
      Props/     {Military, Logistics, Urban, Rural, Coastal}
      Terrain/
    VFX/
    UI/
  Audio/
  Maps/
    Official/
    Templates/       # editör başlangıç şablonları
  _Source/           # Blender .blend, .psd, .svg — build'e dahil değil
```

`_Source/` klasörü Git LFS ile takip edilir; oyun build'ine dahil edilmez.

## Araç Zinciri

| Aşama | Araç |
| --- | --- |
| Modelleme | Blender 4.2 LTS (düşük poligon, flat shading iş akışı) |
| UV / atlas | Blender + özel palet atlas eklentisi |
| Doku / palet | Aseprite (palet), Affinity/Photoshop (UI) |
| Animasyon | Blender; paylaşılan rig üzerinde retarget |
| VFX | Motor içi partikül sistemi + Blender mesh efektleri |
| Motor | Unity 6 LTS, URP Mobile (Polyfield 1 ile devamlılık) — alternatif değerlendirme: Godot 4.6 |
| Sürüm kontrol | Git + Git LFS (`*.blend, *.fbx, *.png, *.wav`) |
| CI | Asset kontrol listesi otomasyonu + gecelik build + cihaz farmında FPS regresyon testi |

## Performans Regresyon Testi

Gecelik CI, 3 referans cihazda 12 resmî haritanın her birinde 60 saniyelik sabit kamera turu koşar ve şunları kaydeder: ortalama FPS, %1 düşük FPS, kare süresi dağılımı, tepe bellek, draw call. Herhangi bir haritada %1 düşük FPS hedefin altına inerse build **kırmızı** işaretlenir. Polyfield 1'in "uneven performance" eleştirisi ancak bu tür sürekli ölçümle kapanır — sürüm sonu optimizasyonuyla değil.
