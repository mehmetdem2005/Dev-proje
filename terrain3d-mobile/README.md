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

Ölçülen değerler uydurma değil — `tools/verify.gd` bunları çalışan eklentiye
karşı doğruluyor, aşağıdaki **Doğrulama** bölümüne bakın.

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
[Demo] objects in frame=41 draw calls=41 prims=31786
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
- Bu paket eklentiyi *yapılandırıyor*, shader'ını yeniden yazmıyor. Daha da
  ileri gitmek isterseniz `material.shader_override_enabled = true` ile üretilen
  shader'ı kaydedip elle budayabilirsiniz.

## Lisans

Terrain3D MIT lisanslı, © Cory Petkovsek, Roope Palmroos ve katkıda bulunanlar.
`addons/terrain_3d/` içeriği orijinal sürümden değiştirilmeden alınmıştır
(sadece kullanılmayan platform ikilileri silinmiştir). Bu depoya eklenen
`mobile/`, `demo/` ve `tools/` dosyaları yapılandırma katmanıdır.
