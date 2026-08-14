# 05 — Üretim Yol Haritası

## Ekip Varsayımı

`03-asset-listesi.md` toplam **~735 adam-gün** görsel/ses üretim işi öngörüyor. Buna oynanış programlaması, ağ altyapısı, backend ve QA dahil değildir.

| Rol | Kişi | Kapsam |
| --- | --- | --- |
| Sanat yönetmeni | 1 | Stil rehberi sahibi, tüm asset onayı |
| Çevre modelci | 3 | Modüler kit, doğa, prop, biyomlar |
| Karakter/araç modelci | 2 | Karakterler, silahlar, araçlar |
| Teknik sanatçı | 1 | Shader, LOD, batching, bütçe otomasyonu |
| Animatör | 1 | Paylaşılan rig, 83 klip |
| VFX sanatçısı | 1 | 45 efekt |
| UI sanatçısı | 1 | 210 kalem + editör arayüzü |
| Level designer | 2 | 12 harita + editör şablonları |
| Ses tasarımcısı | 1 (yarı zamanlı) | 320 ses |

**9.5 kişilik sanat ekibiyle ~735 adam-gün ≈ 78 çalışma günü ≈ 16 hafta net üretim.** Onay turları, revizyon ve entegrasyon payı ile **~26 hafta** planlanır.

## Zaman Çizelgesi

| Faz | Süre | Çıktı | Kapı (geçiş şartı) |
| --- | --- | --- | --- |
| **F0 — Ön üretim** | 4 hafta | Stil rehberi onayı, palet atlası, 3 örnek asset, rig prototipi, teknik bütçe doğrulaması | Sanat yönetmeni + firma onayı |
| **F1 — Dikey dilim** | 6 hafta | Bocage haritası, ABD+Almanya, 8 silah, 2 araç, çekirdek VFX/HUD | Düşük profil cihazda 64 bot ile **30 FPS sabit** |
| **F2 — Çekirdek içerik** | 10 hafta | 4 harita, 4 millet, 24 silah, 10 araç, editör v1 | Kapalı beta, 200 oyuncu, kritik hata yok |
| **F3 — Tam içerik** | 10 hafta | 12 harita, 5 millet, 38 silah, 22 araç, editör tam kütüphane | Bütün haritalar performans regresyon testinden geçer |
| **F4 — Cila ve lansman** | 6 hafta | Optimizasyon, ses karışımı, mağaza görselleri, fragman | Mağaza onayı |
| **F5 — Yaşayan oyun** | Sürekli | 6 haftada 1 harita, sezonluk kozmetik, topluluk harita vitrini | — |

**Toplam lansmana kadar: ~36 hafta (≈ 8.5 ay).**

## Kritik Yol

Aşağıdaki zincir gecikirse tüm plan gecikir. Öncelik burada:

1. **Palet atlası + paylaşılan materyal** — her çevre asset'i buna bağımlı, F0'da bitmeli.
2. **Paylaşılan karakter rig'i** — 83 animasyon klibi ve 5 milletin tamamı buna bağımlı. Rig değişirse tüm animasyon yeniden yapılır. F0'da kilitlenir, sonra dokunulmaz.
3. **Modüler bina kiti ızgara standardı** — 180 parça ve tüm level design buna bağımlı. F0'da 1 m ızgara kararı yazılı olarak kilitlenir.
4. **Dikey dilim performans kanıtı** — F1'de düşük profil cihazda 30 FPS tutturulamazsa, F2'ye geçmeden bütçeler aşağı çekilir. Bu kapı esnetilmez; Polyfield 1'in performans borcu tam olarak bu kapının atlanmasıyla oluşur.

## Riskler ve Karşılıkları

| Risk | Etki | Karşılık |
| --- | --- | --- |
| Düşük cihazlarda 64 oyuncu + araç yükü 30 FPS'i tutturamaz | Yüksek | F1'de erken kanıt; gerekirse Düşük profilde karakter LOD3 mesafesini 80 m'ye çek, araç sayısını sınırla |
| Rig geç kilitlenir, animasyon yeniden yapılır | Yüksek | F0 kapısı; rig değişikliği F1 sonrası **değişiklik talebi** olarak ele alınır |
| 5 millet × 4 sınıf asset patlaması | Orta | Modüler karakter parça sistemi (34 parça → 20 kombinasyon) |
| Editör kütüphanesi büyüdükçe bellek | Orta | Biyom bazlı asset bundle, talep üzerine yükleme |
| Topluluk haritalarının performansı kontrolsüz | Orta | Editörde canlı bütçe sayacı + yayın öncesi performans rozeti |
| Paket boyutu 180 MB hedefini aşar | Orta | Play Asset Delivery; biyomlar talep üzerine |
| Polyfield 1 kaynak dosyaları devralınamaz | Düşük | Plan zaten sıfırdan üretim varsayıyor; takvim etkilenmez |

## Başarı Ölçütleri

| Ölçüt | Polyfield 1 (referans) | Polyfield 2 hedefi |
| --- | --- | --- |
| Düşük cihaz ortalama FPS | Değişken, düşüşler bildiriliyor | 30 sabit, %1 düşük ≥ 26 |
| İlk indirme boyutu | ~257 MB | ≤ 180 MB |
| Lansmanda harita sayısı | 22 (0.7 itibarıyla, zamanla birikmiş) | 12 (yeniden üretilmiş, biyom çeşitliliği ile) |
| Ateşli silah sayısı | ~10 | 38 |
| Araç sayısı | 2 | 22 |
| Cephe görsel tutarlılığı | Şikâyet konusu | Yapısal olarak garantili (kilitli millet kiti) |
| Mağaza puanı | 8.7 / 10 | ≥ 9.0 |

## Bu Dokümanların Kullanımı

- `00` — orijinal oyunun durum tespiti; bir tartışmada "Polyfield 1 nasıldı?" sorusunun cevabı.
- `01` — sanat kararlarının tek doğruluk kaynağı. Bir asset reddedildiğinde gerekçe buradan verilir.
- `02` — level design ve harita editörü ekibinin çalışma çerçevesi.
- `03` — üretim planlaması ve iş dağıtımının temeli; her kalem bir görev olarak takip sistemine açılır.
- `04` — teknik sanat ve CI kurallarının kaynağı; asset kabul kontrol listesi buradan otomasyona dökülür.
- `05` — takvim, ekip ve kapılar.

Değişiklik önerileri, ilgili dokümana pull request olarak açılır ve sanat yönetmeni onayından geçer. Bütçe rakamları (poligon, draw call, bellek) **sanat yönetmeni + teknik sanatçı ortak onayı** olmadan değiştirilmez.
