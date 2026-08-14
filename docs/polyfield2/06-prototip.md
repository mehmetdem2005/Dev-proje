# 06 — Çalışan Prototip: "Ridgeline"

`00`–`05` dokümanları Polyfield 1'in birebir devamı olan bir 2. Dünya Savaşı
sürümünü planlıyordu. Sonraki karar oyunu **aynısı olmayacak şekilde
farklılaştırmaktı**; bu doküman fiilen inşa edilen prototipi ve plandan
ayrıldığı yerleri kaydeder.

Kod ve varlıklar: [`polyfield2/`](../../polyfield2/) — kurulum ve üretim
komutları için [`polyfield2/README.md`](../../polyfield2/README.md).

## Plandan Sapmalar

| Konu | Plan (00–05) | Prototipte yapılan | Gerekçe |
| --- | --- | --- | --- |
| Motor | Unity 6 LTS (Polyfield 1 devamlılığı) | **Godot 4.6.3, Mobile renderer** | Doğrudan talep |
| Dönem | Gerçek 2. Dünya Savaşı, 5 millet | Kurgusal iki cephe: **Ridge Rangers / Iron Legion** | "Aynısı olmasın" |
| Malzeme akışı | PBR yok, sadece renk paleti | **Tam PBR: albedo + normal + ORM + height** | Doğrudan talep ("her texture'ı map dosyalarıyla") |
| Biyom | 6 biyom | 1 biyom: **kayalık yayla** | Talep edilen harita tipi |
| Harita | 12 harita | 1 harita: **Ridgeline**, 192 × 192 m | Prototip kapsamı |
| Asset kaynağı | Karma (modelci ekibi) | **Tamamı Blender'da prosedürel üretim** | Doğrudan talep |

Sabit kalanlar: 5 bölgeli Territory Control, siluet önceliği, düşük poligon
bütçeleri, tek paylaşılan doku atlası mantığı, kilitli cephe kiti ilkesi.

## Üretilen Varlıklar

**13 malzeme × 4 harita = 52 PNG.** Doku üreteci saf numpy; kendi PNG
yazıcısı ve döşenebilir gürültü kütüphanesi var, harici bağımlılık yok.
Worley gürültüsü 3×3 hücre komşuluğu ve F2−F1 hücre kenarı ile hesaplanıyor —
bu hem üretimi ~20 kat hızlandırdı hem de lekeleri gerçek çatlak ağına
çevirdi.

**Meshler:** arazi (73 728 üçgen, 16 chunk), 5 kaya + 2 kayalık blok,
revetmanlı siper bölmesi + kum torbası duvarı/yığını + tank engeli + sığınak
çatısı, sandık/varil/cephane kutusu/bölge direği, 5 silah, 2 cepheye ait
riglenmiş asker.

**Rig:** 24 kemik (sağ elde `WeaponSocket` dahil), ağırlıklar kemik-segment
mesafesiyle veriliyor. Blender'ın heat weighting'i su geçirmez bağlı geometri
istiyor; ayrı uzuv prizmalarından kurulmuş bir figürde çalışmıyor.

**Animasyon:** `idle`, `walk`, `run`, `crouch_idle`, `crouch_walk`, `aim`,
`fire`, `reload`, `hit`, `death`, `jump`.

## Harita

Kayalık yayla, dolambaçlı bir sırt, 7 kaya çıkıntısı, 5 ele geçirme bölgesi
(A–E), parapetli 8 siper hattı, 6 krater ve kayalık sınır kuşağı. Oynanabilir
alanın **%77'si 35° altında yürünebilir**; her bölge medyan eğimi 13°'nin
altına düzleştirilmiş.

Siperler arazide oyuluyor, revetman/duckboard/ateş basamağı ise ayrı modül
olarak aynı polylinelara yerleştiriliyor — ikisi de `layout.py`'den okuduğu
için birbirinden kayması mümkün değil.

## Motor Tarafı

- Doğrulandı: **Vulkan — Forward Mobile**.
- Seviye kurulumu ~200 ms; tekrar eden geometri `MultiMeshInstance3D` ile,
  sahne toplam **~154 draw call**.
- Dokunmatik HUD kodda kuruluyor: sol başparmak sanal çubuk, sağ başparmak
  bakış, ateş/nişan/çömel/zıpla/koş/şarjör. Çoklu dokunuş parmak indeksiyle
  izleniyor, aynı anda yürüyüp bakmak çalışıyor.
- Territory Control tek bir −1..+1 çekişme barı ile: çekişmeli bölge duruyor,
  yarım alınmış bölge kimseye puan yazmıyor.

## Doğrulama

Her üretim adımı görsel olarak kontrol edildi; iki headless araç var:
`tools/blender/preview.py` (GLB render) ve oyunun içindeki `--shot` modu
(çalışan oyunun ekran görüntüsü + kare istatistikleri). Bu döngüde yakalanan
ve düzeltilen gerçek hatalar:

- Worley gürültüsü bloblar üretiyordu → hücre kenarı (F2−F1) yaklaşımı
- Arazi düz bir tepsiydi → ridged gürültü tabanı, sonra aşırıya kaçınca geri alındı
- `_bevelled_box` tam ölçü alırken bazı çağrılar yarım ölçü varsaymış → sandık patlamıştı
- Üsler sınır kuşağının yamacına denk geliyordu → oyuncu tepenin içinde doğuyordu
- Viewmodel dünya ölçeğinde render oluyordu → ekranın yarısını kaplıyordu
- Cephe aksan şeridi atlas bandı vücut parçalarına hizalı olmadığı için
  **askerin yüzüne** denk geliyordu → cloth/skin/gear olarak üç ayrı bant

## Bilinen Eksikler

- Elle yazılmış LOD zinciri yok; Godot'un otomatik mesh LOD'u kullanılıyor.
- Botlar navmesh değil düz çizgi güdümü kullanıyor; kayaya dayanıp kalabiliyor.
- Ses yok.
- Asker oranlarında bacaklar gövdeye göre hâlâ bir miktar uzun.
