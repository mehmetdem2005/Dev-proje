# 02 — Polyfield 2 Dünya Tasarımı

## Dünya Kurgusu

Polyfield 2 tek bir sürekli açık dünya değildir. Polyfield 1'in doğru kararı olan **ayrık, elle kurulmuş savaş alanları** korunur; gelişme *ölçekte* değil, **biyom çeşitliliği, dikey katman ve yıkılabilirlikte** aranır.

Kurgu çerçevesi: 1941–1945 arası dört cephe. Her cephe bir **biyom kimliği**, bir **millet eşleşmesi** ve bir **ışık senaryosu** taşır.

## Biyomlar

| # | Biyom | Cephe | Milletler | Palet ekseni | Sis mesafesi |
| --- | --- | --- | --- | --- | --- |
| 1 | **Normandiya Bocage** | Batı 1944 | ABD / Almanya | Yeşil-toprak | 220 m |
| 2 | **Doğu Cephesi Kışı** | Doğu 1942 | SSCB / Almanya | Beyaz-gri-kırmızı | 140 m (kar fırtınası) |
| 3 | **Kuzey Afrika Çölü** | Afrika 1942 | İngiltere / Almanya | Kum-turkuaz | 320 m (açık) |
| 4 | **Pasifik Adası** | Pasifik 1944 | ABD / Japonya | Yeşil-turkuaz | 180 m |
| 5 | **Kent Yıkıntısı** | Doğu/Batı 1945 | SSCB / Almanya | Gri-tuğla-turuncu | 160 m (toz) |
| 6 | **Alp Geçidi** | İtalya 1944 | ABD / Almanya | Kaya-çam-kar | 260 m |

Biyomlar hem resmî haritalarda hem de **harita editöründe seçilebilir tema paketleri** olarak sunulur. Editör kullanıcısı biyomu değiştirdiğinde arazi malzemesi, sis, ışık ve prop kütüphanesi topluca değişir — Polyfield 1'de en çok istenen editör özelliği bu.

## Harita Ölçeği ve Katmanlar

64 oyunculuk Territory Control için doğrulanmış ölçek:

| Parametre | Değer |
| --- | --- |
| Harita alanı | 1000 × 1000 m (ana), 600 × 600 m (yoğun kent) |
| Capture bölgesi | 5 adet (A–E), Polyfield 1 ile uyumlu |
| Bölgeler arası mesafe | 120–180 m (koşu süresi 25–40 sn) |
| Spawn → ilk bölge | ≤ 60 m, ≤ 15 sn |
| Yükseklik farkı | 0–45 m; her haritada en az 2 farklı kot |
| Dikey erişim | Her bölgede en az 1 üst kat / tepe pozisyonu |

**Beş bölgeli iskelet:** A ve E takım üsleri yakınında (savunma çapası), B ve D yan kanat (flanking çekişmesi), C merkez (yüksek riskli, açık ve dikey). Bu düzen Polyfield 1'in "hold ederek puan" ekonomisiyle birebir uyumlu ve dengeli bir kaymayı garanti eder.

**Üç şerit kuralı:** Her bölge çiftinin arasında birbirinden görsel olarak ayrılabilen üç yaklaşım şeridi bulunur — açık (hızlı, riskli), kapalı (yavaş, korunaklı), dikey (yüksek görüş, sınırlı çıkış). Tek şeritli koridor tasarımı yasaktır.

## Lansman Harita Listesi (12 harita)

| Harita | Biyom | Boyut | Işık | Öne çıkan mekanik |
| --- | --- | --- | --- | --- |
| Bocage | Normandiya | 1000² | Öğle | Çit labirenti, tank görüş kısıtı |
| Sainte-Colline | Normandiya | 800² | Sabah sisi | Tepedeki kilise, çan kulesi keskin nişancı |
| Omaha Landing | Normandiya | 1000² | Şafak | Asimetrik çıkarma, sahil→uçurum saldırısı |
| Rzhev Kışı | Doğu Kışı | 1000² | Kar fırtınası | Görüş 140 m, sıcak sığınaklar |
| Traktör Fabrikası | Kent Yıkıntısı | 600² | Kapalı hava | 3 katlı iç mekân, yıkılabilir duvarlar |
| Baronstadt Yıkıntısı* | Kent Yıkıntısı | 800² | Altın saat | Kanal geçişleri, moloz siperleri |
| Gazala Kumu | Kuzey Afrika | 1000² | Sert öğle | Açık tank muharebesi, uzun görüş |
| Vaha Karargâhı | Kuzey Afrika | 700² | Gün batımı | Sıkışık kerpiç yerleşim |
| Mercan Koyu | Pasifik | 900² | Öğle | Su geçişleri, bunker hattı |
| Kereste Sırtı | Pasifik | 700² | Yağmur | Yoğun bitki örtüsü, kısa mesafe |
| Verdun Kalesi* | Alp | 800² | Bulutlu | Tarihî istihkâm, tünel ağı |
| Açık Alan* | Normandiya | 1000² | Nötr | Editör başlangıç şablonu / test |

\* Polyfield 1'den devralınan ve yeniden yorumlanan haritalar (Baronstadt, Fort Verdun, OpenField). Topluluğun tanıdığı isimler korunur; düzen ve assetler yeniden üretilir.

**Lansman sonrası:** 6 haftada bir 1 harita, biyom rotasyonuyla. Hedef 12 ay sonunda 20 resmî harita.

## Arazi Sistemi

- **Heightmap tabanlı, 2 m çözünürlüklü ızgara.** 1000 m harita = 500 × 500 vertex, 4 chunk'a bölünür.
- Arazi malzemesi **vertex color splat** (4 kanal: toprak / çim / kaya / kar-kum). Doku birleştirme yok, renk karışımı var.
- **Chunk başına frustum + mesafe culling.** Uzak chunk'lar tek LOD seviyesine düşer.
- Editörde arazi araçları: yükselt, alçalt, düzle, yumuşat, boya (4 kanal), su seviyesi.

## Yıkılabilirlik

Polyfield 1'in 0.7 ile eklediği yıkım fiziği genişletilir, ancak **sınırlı ve kasıtlı** tutulur:

| Katman | Davranış |
| --- | --- |
| Prop yıkımı | Çit, varil, sandık, telefon direği → parçalara ayrılır, 8 sn sonra silinir |
| Duvar delme | Önceden tanımlı "kırılabilir panel"ler; patlayıcı ile açılır, kalıcı |
| Bina çökmesi | Yok — ağ senkronizasyon maliyeti kabul edilmiyor |
| Arazi krateri | Sadece görsel decal + yerel vertex bastırma (maks. 32 aktif) |

Yıkım durumu sunucu otoriter, kalıcı ve maç sonunda sıfırlanır. Yıkılabilir her obje harita bütçesinde ayrı sayılır (bkz. `04-teknik-butce-pipeline.md`).

## Harita Editörü — Polyfield 2 Gelişmeleri

Editör, Polyfield 1'in en güçlü tutundurma özelliği. Polyfield 2'de birinci sınıf ürün olarak ele alınır:

1. **Biyom teması seçici** — tek tıkla tüm haritanın palet/ışık/prop kütüphanesi değişir.
2. **Kategorili prop tarayıcısı** — arama, etiket, favori, son kullanılanlar.
3. **Modüler bina kiti** — 1 m ızgaraya kilitlenen duvar/kapı/pencere/çatı parçaları.
4. **Prefab grupları** — birden çok objeyi grupla, kaydet, tekrar kullan.
5. **Denge analiz aracı** (0.7.5'teki "analyzer"ın devamı) — spawn mesafeleri, bölge kapsama alanı, görüş hattı ısı haritası, poligon/draw-call sayacı **canlı** gösterilir.
6. **Performans rozeti** — harita yayınlanmadan önce bütçe kontrolünden geçer; "Düşük cihaz uyumlu / Yüksek cihaz gerektirir" etiketi alır.
7. **Paylaşım** — oyun içi harita tarayıcısı, oy verme, rapor. (Topluluğun `pf-tool` gibi harici araçlara mecbur kalması bir üründeki boşluğun kanıtıdır; bu boşluk kapatılır.)

## Ses Atmosferi (özet)

Görsel plan kapsamı dışı ama biyom kimliğinin yarısı sestir:

- Her biyomun kendi ortam döngüsü (kuş/rüzgâr/uzak topçu/dalga).
- Mesafeye göre 3 katmanlı silah sesi: yakın / orta / uzak yankı.
- Kapalı mekânda reverb bölgeleri, editörde yerleştirilebilir.
