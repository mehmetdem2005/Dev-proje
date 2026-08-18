# Terrain3D Mobile

[Terrain3D](https://github.com/TokisanGames/Terrain3D) **v1.0.2-stable**, orijinal
eklentinin kendisi, telefon için sınırlandırılmış ve kısılmış hâlde.

Terrain3D masaüstü açık dünyalar için ayarlanmış geliyor. Kutudan çıktığı hâliyle
**7 LOD'luk bir clipmap** kuruyor — yani **144 MeshInstance** — ve yaklaşık
**12 km** genişliğe uzanıyor. Verinin bittiği yerden sonrasını da prosedürel
gürültüyle dolduruyor, bu yüzden dünya sonsuz görünüyor. Telefonda bunun üçü de
yanlış, ve bu paket üçünü de düzeltiyor.

| | Orijinal ayar | Bu paket (512 m dünya) |
| --- | --- | --- |
| MeshInstance | **144** | **64** |
| Ulaştığı mesafe | **12 288 m** | **512–576 m** |
| Dünya arka planı | `NOISE` (sonsuz) | `NONE` (haritanın gerçek kenarı var) |
| `auto_shader` | açık | kapalı |
| `dual_scaling` | açık | kapalı |
| Arazi gölgesi | açık | kapalı (LOW/MEDIUM) |

Ayrıca **32 hazır yeryüzü texture'ı** paketin içinde — CC0, mobil boyutta,
Terrain3D'nin kanal düzenine göre paketlenmiş, sıkıştırılmış ve `.tres` olarak
hazır. Açıp boyamaya başlayabilirsin.

Ölçülen değerler uydurma değil — `tools/verify.gd` bunları çalışan eklentiye
karşı doğruluyor, aşağıdaki **Doğrulama** bölümüne bakın.

## Texture paketi

**32 texture** — Terrain3D'nin dizi sınırı da tam olarak 32. Hepsi CC0
(ambientCG), 512×512, kaynakları `textures/SOURCES.md` içinde tek tek yazılı.

| Kategori | Adet | Örnekler |
| --- | --- | --- |
| Kaya / kayalık | 11 | `rock_granite`, `rock_strata`, `cliff_layered`, `rock_slate` |
| Toprak / çamur | 10 | `dirt_dry`, `soil_dark`, `mud_wet`, `leaf_litter` |
| Çim | 4 | `grass_meadow`, `grass_dry`, `grass_tufted`, `grass_patchy` |
| Çakıl / moloz | 4 | `gravel_grey`, `scree_slope`, `gravel_river` |
| Kar | 2 | `snow_fresh`, `snow_packed` |
| Kum | 1 | `sand_fine` |

Hepsinin **height, normal ve roughness** haritası var. `terrain3d_assets.tres`
hazır — `Terrain3D.assets` alanına sürükle, 32'si birden gelir.

### Kanal düzeni

Terrain3D gevşek PBR haritaları almıyor. Tam olarak iki texture dizisi
örnekliyor ve her birinden dört kanal okuyor:

```
<isim>_alb_ht.png    RGB = albedo (sRGB),  A = height
<isim>_nrm_rg.png    RGB = normal (OpenGL), A = roughness
```

Alfa kanalları boşluk doldurmuyor. `albedo.a`, bir malzemeyi diğerinin üstüne
karıştırırken kullanılan yükseklik — çakılın kayanın çatlaklarına oturmasını
sağlayan şey bu, yoksa iki doku birbirine solar. `normal.a` ise roughness.
İkisinden birini yanlış paketlersen sonuç doku hatası gibi değil, **ışıklandırma
hatası** gibi görünür.

Kendi texture'ını eklemek istersen:

```bash
blender -b --python tools/fetch_textures.py -- --size 512 --count 32
python3 tools/fix_imports.py
godot --headless --import
godot --headless -s tools/build_assets.gd
```

Dizideki her texture **aynı boyut, aynı format ve aynı mipmap ayarında**
olmalı. Biri farklıysa Terrain3D dizi kurmayı reddeder ve konsola uyarı basar.

## Kurulum

1. `addons/terrain_3d/` klasörünü projenize kopyalayın.
2. `mobile/terrain3d_mobile.gd` dosyasını da kopyalayın.
3. Godot'u açın → **Project > Project Settings > Plugins** → Terrain3D'yi
   etkinleştirin → **editörü yeniden başlatın** (GDExtension yüklenmesi için şart).
4. Proje ayarlarında:
   - `rendering/renderer/rendering_method = "mobile"`
   - `rendering/textures/vram_compression/import_etc2_astc = true` ← Android'de
     **zorunlu**, yoksa doku dizileri cihazda yüklenmez.

Bu depodaki proje zaten böyle ayarlı; doğrudan açıp çalıştırabilirsiniz.

## Kullanım

`Terrain3D` düğümünüzün altına bir `Terrain3DMobile` düğümü koyun:

```
Terrain3D
  └─ Terrain3DMobile      world_size_m = 512, tier = MEDIUM
```

`apply` kutusunu işaretleyin. Ne yaptığını konsola yazar. Ya da koddan:

```gdscript
var report := Terrain3DMobile.configure($Terrain3D, 512.0, Terrain3DMobile.Tier.MEDIUM)
print(Terrain3DMobile.format_report(report))
```

Çıktı:

```
[Terrain3DMobile] tier MEDIUM
  clipmap      3 LODs x 24 quads @ 1.50 m/vertex
  MeshInstances 64   (stock Terrain3D: 144)
  reaches      576 m   (asked for 512 m, stock reaches 12288 m)
  background   NONE — terrain stops at your regions
  shadows      off   collision on
```

### `world_size_m` — "sadece belirlediğimiz kadar"

Tek önemli düğme bu. İstediğiniz dünya genişliğini metre olarak yazarsınız,
script clipmap'i **tam onu kaplayacak kadar** kurar, fazlasını değil.

LOD sayısı buradan çıkar, siz seçmezsiniz:

```
kapsama = 4 × mesh_size × 2^(lods−1) × vertex_spacing
```

LOD0 `mesh_size` karolu 4×4'lük bir ızgara seriyor, üstündeki her LOD ölçeği iki
katına çıkarıyor. Yani her LOD dünyayı iki katına çıkarır — 7 LOD'un 12 km
yapmasının sebebi bu, sihir değil.

### MeshInstance sayısı

Doğrudan `Terrain3DMesher`'dan çıkan bir formül, tahmin değil:

```
MeshInstance = 24 + 20 × (mesh_lods − 1)
```

LOD0: 16 karo + 2 + 2 kenar + 2 + 2 trim = **24**
LOD1+: her biri 12 karo + 2 + 2 kenar + 2 + 2 dolgu = **20**

| `mesh_lods` | MeshInstance |
| --- | --- |
| 1 | 24 |
| 2 | 44 |
| **3** | **64** |
| 4 | 84 |
| 7 (orijinal) | 144 |

### Kaliteler

`tier` MeshInstance sayısını değiştirmez — onu `world_size_m` belirler. Tier,
**vertex yoğunluğunu ve shader'ın isteğe bağlı geçişlerini** ayarlar; asıl
pahalı olanlar bunlar.

| | LOW | MEDIUM | HIGH |
| --- | --- | --- | --- |
| `mesh_size` | 16 | 24 | 32 |
| `vertex_spacing` | 2.0 m | 1.5 m | 1.0 m |
| en fazla LOD | 3 | 4 | 5 |
| arazi gölgesi | kapalı | kapalı | açık |
| düz normaller | açık | kapalı | kapalı |
| triplanar projeksiyon | kapalı | kapalı | açık |
| makro varyasyon | kapalı | kapalı | açık |

## En büyük bellek kazancı: import ayarları

Godot texture'ları varsayılan olarak **Lossless ve mipmap'siz** içe aktarır.
Terrain3D ise kaynak formatı olduğu gibi kendi texture dizisine kopyalar. Yani
varsayılan ayarlarla:

| | Varsayılan Godot importu | `tools/fix_imports.py` sonrası |
| --- | --- | --- |
| Format | RGBA8 (sıkıştırılmamış) | DXT5 / ETC2 / ASTC |
| Mipmap | yok | var |
| **32 texture × 2 dizi** | **~85 MB VRAM** | **21.3 MB VRAM** |

Sadece zeminin **64 MB VRAM** fazladan yemesi demekti bu. Telefonda kasmanın —
hatta çökmenin — en olası tek sebebi.

Üç ayar:

- `compress/mode=2` → Android'de ETC2/ASTC.
- `mipmaps/generate=true` → mipmap olmadan uzaktaki her piksel tam çözünürlüğü
  örnekler, texture cache'i döver ve kamera oynadıkça parlar. Terrain3D
  `textureGrad` ile örnekliyor, yani mipmap bekliyor.
- `compress/normal_map=2` (Disabled) → "Detect", alfayı atan bir normal-map
  codec'i seçebilir. `*_nrm_rg.png`'nin alfası **roughness**. Sessizce
  kaybedersen bütün arazi tek tip parlak olur.

Bu ayarlar `.import` dosyalarında; texture eklersen scripti tekrar çalıştır.

## Mobil shader override

Terrain3D'nin **anizotropik olmayan bir yolu yok**: `texture_filtering`'in her
iki seçeneği de (`Linear` ve `Nearest`) anizotropik sampler kullanıyor —
`uniforms.glsl` içinde sabit. Ekranı dolduran bir yüzeyde iki texture dizisini
anizotropik örneklemek, telefonun sahip olmadığı bant genişliği demek.

Eklentinin kendi ayarlarıyla bu kapatılamıyor, o yüzden paket üretilmiş
shader'ı override ediyor:

```
filter_linear_mipmap_anisotropic  →  filter_linear_mipmap     (4 sampler)
```

`mobile/terrain3d_mobile.gdshader` bu shader. Terrain3D shader'ını açık
özelliklere göre çalışma anında birleştirdiği için, bu dosya **mobil özellik
seti** için üretildi (`world_background` NONE, `auto_shader` kapalı,
`dual_scaling` kapalı) — o bloklar shader'ın içinde hiç yok, yorum satırı bile
değil.

Bu özelliklerden birini geri açarsan shader onu yansıtmaz. Ya yeniden üret:

```bash
godot --headless --quit-after 20 tools/dump_shader.tscn
```

ya da `use_mobile_shader = false` yap.

## Neyi neden kapattım

Hepsi ekranın çoğunu kaplayan bir yüzeyde **piksel başına** çalışan şeyler.
Telefonda pahalı olan da tam olarak bu.

- **`world_background = NONE`** — "sonsuz görünme" sorununun asıl ayarı.
  `NOISE`, bölgelerinizin dışındaki her yeri ufka kadar prosedürel araziyle
  doldurur *ve* fragment shader'ına koca bir gürültü bloğu ekler. `NONE` ile
  arazi sadece bölgelerinizin olduğu yerde var olur — haritanın gerçek bir
  kenarı olur. Terrain3D bu blokları shader'a sadece açıkken derlediği için
  kapatmak hem görüntüyü sınırlar hem shader'ı küçültür.
- **`auto_shader = false`** — dokuları eğime göre otomatik harmanlar, ekstra
  dallanma ve doku okuması demek.
- **`dual_scaling = false`** — aynı dokuyu iki ölçekte okuyup karıştırır, yani
  doku okumalarını ikiye katlar.
- **`enable_projection = false`** — dik yüzeylerde triplanar projeksiyon;
  oralarda okuma sayısını üçe katlar.
- **`enable_macro_variation = false`** — piksel başına iki ekstra gürültü okuması.
- **`depth_blur = 0`** — bağımlı doku okuması (dependent texture read). Mobilde
  asla.
- **`cast_shadows = Off`** (LOW/MEDIUM) — arazi gölgesi, ekranı dolduran bir
  yüzeyin ikinci kez çizilmesi demek. Arazinin üstündeki nesneler gölgesini
  araziye yine düşürür, kaybettiğiniz sadece arazinin kendi üstüne gölgesi.
- **`texture_filtering = LINEAR`** — anizotropik filtreleme mobil bant
  genişliğini yer.
- **`gi_mode = Disabled`** — mobilde global illumination zaten kullanılmıyor.
- **`bias_distance`** — shader'ın küçük mipmap'lere geçmeye başladığı mesafe.
  Terrain3D'nin varsayılanı 512 m; sınırlı bir haritada bu zaten dünyanın
  dışında kalıyor, yani hiç devreye girmiyordu. Kaliteye göre 96–320 m.
- **`anisotropic_filtering_level=0`** (proje ayarı) — Godot global anizotropiyi
  varsayılan 2x veriyor ve bu her dokulu yüzeyde ödeniyor.
- **Yönlü gölge atlası 2048 → 1024** — sınırlı bir harita için fazlasıyla
  yeterli, hem bellekten hem gölge geçişinin dolgu maliyetinden kazandırıyor.

## Doğrulama

```bash
godot --headless -s tools/verify.gd
```

README'deki her sayı bir iddia ve Terrain3D derlenmiş bir eklenti — altımızdan
değişebilir. Bu yüzden verify, okuduğum kaynağa değil **çalışan eklentiye**
karşı test ediyor: ayarların gerçekten uygulandığını, `world_background`'ın 0
olduğunu, instance sayısının sınırlı kaldığını.

```
=== Terrain3D mobile configuration ===
[clipmap maths]
  ok    stock instances (7 LODs)           144
  ok    stock coverage m                   12288
  ok    3 LOD instances                    64
[MEDIUM]
  ok    mesh_lods applied                  3
  ok    world_background NONE              0
  ok    auto_shader off                    false
  ->    64 MeshInstances, reaches 576 m
VERIFY PASS
```

Demo sahnesi (`demo/mobile_demo.tscn`) çalışan oyunda ölçüyor. Vulkan Forward
Mobile ile, boş veriyle (henüz bölge oluşturulmamış):

```
[Demo] renderer: Vulkan — Forward Mobile
[Demo] mesh_lods=3 mesh_size=24 vertex_spacing=1.5
[Demo] material world_background=0 (0=None 1=Flat 2=Noise)
[Demo] textures loaded=32
[Demo] objects in frame=41 draw calls=41 prims=31786
```

Texture belleği de doğrulanıyor:

```
[texture memory]
  albedo         512x512 DXT5       mips=true  x32 =  10.7 MB
  normal         512x512 DXT5       mips=true  x32 =  10.7 MB
  arrays total   21.3 MB  (uncompressed would be ~85 MB)
```

64 instance'ın 41'i karede — gerisini frustum eliyor. Harita verisi
eklediğinizde primitif sayısı artacaktır; ölçüyü kendi haritanızla tekrarlayın.

## İkili dosyalar

Resmî v1.0.2-stable sürümünden, gereksiz platformlar atılmış:

| Dosya | Ne için |
| --- | --- |
| `libterrain.android.release.arm64.so` | telefon, release export |
| `libterrain.android.debug.arm64.so` | telefon, debug export |
| `libterrain.linux.*.x86_64.so` | Linux'ta editör |
| `libterrain.windows.*.x86_64.dll` | Windows'ta editör |

arm32, iOS, macOS ve web ikilileri çıkarıldı. Gerekirse
[resmî sürümden](https://github.com/TokisanGames/Terrain3D/releases) geri
alabilirsiniz — `terrain.gdextension` girdileri duruyor.

Kendi masaüstünüz Windows değilse `windows.*.dll` dosyalarını silebilirsiniz
(7.8 MB), Linux değilse `linux.*.so` (7.1 MB). Android ikilileri APK için şart.
Editör fırçaları (`addons/terrain_3d/brushes/`, 12 MB) sadece editörde gerekli;
`export_presets.cfg` bunları APK'dan zaten çıkarıyor.

## Bilinen sınırlar

- **Compatibility (GLES3) renderer desteklenmiyor** — bu paket Vulkan Forward
  Mobile hedefliyor. Terrain3D 1.0+ Compatibility desteği iddia ediyor ama
  Godot 4.4+ gerektiriyor ve hâlâ kırılgan.
- **Bazı cihazlar doku dizilerini (texture array) tam desteklemiyor.**
  Terrain3D dokularını doku dizisi olarak okuyor; sorun yaşarsanız önce
  `import_etc2_astc` ayarını doğrulayın.
- **DDS kullanmayın**, Godot'un içe aktardığı PNG/TGA kullanın.
- **Kamerayı vermeyi unutma.** Terrain3D clipmap'i bir kameraya göre kaydırır.
  `Terrain3D.set_camera(kameran)` çağırmazsan `_physics_process`'ini kapatıp
  hata basar ve zemin oyuncuyla birlikte hareket etmez — ama görüntü çizilmeye
  devam ettiği için fark etmesi zordur. Yapılandırıcı bunu uyarı olarak
  söylüyor. (v1.0.2'de bu bir metot; `clipmap_target` özelliği 1.1 ile geliyor.)
- Texture dizisi 32 ile sınırlı ve hepsi bellekte durur. 32'ye ihtiyacın yoksa
  `textures/SOURCES.json` içinden çıkar ve `tools/build_assets.gd`'yi tekrar
  çalıştır; her texture çifti ~0.7 MB VRAM.

## Lisans

Terrain3D MIT lisanslı, © Cory Petkovsek, Roope Palmroos ve katkıda bulunanlar.
`addons/terrain_3d/` içeriği orijinal sürümden değiştirilmeden alınmıştır
(sadece kullanılmayan platform ikilileri silinmiştir). Bu depoya eklenen
`mobile/`, `demo/` ve `tools/` dosyaları yapılandırma katmanıdır.
