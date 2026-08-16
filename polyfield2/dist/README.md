# Yayınlanan APK'lar

Bu klasör **sürümlenmiş** APK'ları taşır — her yapı değil. GitHub Release
oluşturma bu depoda kullanılamadığı için binary'ler doğrudan depoda tutuluyor;
her dosya git geçmişinde kalıcıdır, o yüzden buraya sadece paylaşılacak sürümler
konur. Günlük yapılar `../build/` altında kalır ve gitignore'dadır.

| Dosya | Sürüm | Boyut | SHA-256 |
| --- | --- | --- | --- |
| `polyfield2-ridgeline-v0.4.0.apk` | 0.4.0 (code 4) | 62 MB | `0f919742ceef658aa01af13ab498755ff55ab3e1fa75d664d78575f24a72739b` |

Yalnızca en son sürüm tutulur — her binary git geçmişinde kalıcı olduğu için
eskiler siliniyor.

## Kurulum

Telefona indirin ve açın. Android "bilinmeyen kaynaklardan yükleme" izni
isteyecektir.

| | |
| --- | --- |
| Paket | `com.mehmetdem.polyfield2` |
| ABI | arm64-v8a (64-bit ARM; x86 emülatörde çalışmaz) |
| Target SDK | 36 |
| Renderer | Vulkan, Forward Mobile |
| İzinler | VIBRATE, WAKE_LOCK — ağ ve depolama izni yok |

Debug anahtarıyla imzalıdır: sideload ve test için uygundur, Play Store yükleme
anahtarı olarak kullanılamaz.

## Doğrulama

```bash
sha256sum -c SHA256SUMS.txt
```

## Yeniden üretme

```bash
export ANDROID_SDK_ROOT=/path/to/android-sdk
export GODOT_ANDROID_KEYSTORE=/path/to/debug.keystore
../tools/export_apk.sh
```
