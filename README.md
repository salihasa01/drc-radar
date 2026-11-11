# DRC Güvenlik Radarı

BBC, Reuters, AP, Al Jazeera, France 24 ve RFI'dan Kongo Demokratik Cumhuriyeti'ne ait emniyet ve güvenlik haberlerini her 30 dakikada bir süzen, Android telefona uygulama gibi kurulan ücretsiz bir sistem.

## Nasıl çalışır?

```
GitHub Actions (30 dk'da bir)  →  scripts/fetch.py  →  docs/news.json
                                    (RSS çek + süz)          ↓
                                                    GitHub Pages (docs/)
                                                             ↓
                                              Android telefon: ana ekran uygulaması
                                              (+ isteğe bağlı Telegram bildirimi)
```

Sunucu, ücret ya da Play Store gerekmez.

## Kurulum (yaklaşık 10 dakika, bilgisayardan)

1. **GitHub hesabı** açın (github.com, ücretsiz).
2. **Yeni repo** oluşturun: *New repository* → ad: `haber-radar` → **Public** → *Create*.
   > Ücretsiz GitHub Pages için repo'nun herkese açık (Public) olması gerekir. Repoda yalnızca açık kaynak haber başlıkları ve anahtar kelime listesi bulunur.
3. Bu klasördeki tüm dosyaları repoya yükleyin: *Add file → Upload files*, ardından klasörün içeriğini sürükleyin.
   `.github` klasörü gizli olabilir; yüklendiğini kontrol edin. Görünmüyorsa repoda *Add file → Create new file* seçin, ad olarak `.github/workflows/update.yml` yazın ve içeriği yapıştırın.
4. **Actions yazma izni:** *Settings → Actions → General → Workflow permissions* → **Read and write permissions** → *Save*.
5. **Pages'i açın:** *Settings → Pages → Source: Deploy from a branch* → Branch: `main`, klasör: `/docs` → *Save*.
6. **İlk taramayı başlatın:** *Actions* sekmesi → "Haberleri guncelle" → *Run workflow*.
7. Birkaç dakika sonra adres hazır olur: `https://KULLANICIADINIZ.github.io/haber-radar/`

## Telefona kurma (Android)

1. Bu adresi telefonda **Chrome** ile açın.
2. Sağ üstteki ⋮ menüsünden **"Ana ekrana ekle"** ya da **"Uygulamayı yükle"** seçeneğine dokunun.
3. Uygulama ana ekranda simgesiyle görünür ve tam ekran açılır.

## Telegram bildirimi (isteğe bağlı, önerilir)

Önemli bir haber çıktığında telefonunuza anlık bildirim gelir.

1. Telegram'da **@BotFather** ile konuşun, `/newbot` komutuyla bir bot oluşturun ve verilen **token**'ı kopyalayın.
2. Oluşturduğunuz bota bir mesaj yazın (ör. "merhaba").
3. Tarayıcıda `https://api.telegram.org/bot<TOKEN>/getUpdates` adresini açın ve `"chat":{"id": 123456789` kısmındaki sayıyı kopyalayın.
4. GitHub repo → *Settings → Secrets and variables → Actions → New repository secret*:
   - `TELEGRAM_BOT_TOKEN` = token
   - `TELEGRAM_CHAT_ID` = chat id
5. `config.yaml` içindeki `notify:` ayarı: `high` (sadece önemli haberler), `all` (her haber) ya da `off` (kapalı).

## Kaynak ve konu değiştirme

Bütün ayarlar **`config.yaml`** dosyasındadır. Dosyayı GitHub'da açıp ✏️ ile düzenleyebilirsiniz.

- **Yeni site eklemek:** `sources` listesine `name` ve `url` içeren iki satır ekleyin.
  - Sitenin RSS adresi yoksa Google News yöntemini kullanın (Reuters/AP satırlarını örnek alın, `site:` kısmını değiştirin).
- **Yeni anahtar kelime:** `country_terms`, `strong_terms` ya da `security_terms` listesine ekleyin.
- **Süzme kuralı:** haber *(ülke terimi + güvenlik terimi)* ya da *(güçlü terim: M23, ADF, FARDC, MONUSCO…)* içermelidir.
- `*` ile biten terim kök olarak eşleşir (`evacuat*` → evacuate, evacuation).
- Aynı yapıyla başka bir ülke ya da konu için ikinci bir radar kurmak üzere repoyu kopyalayıp `config.yaml` dosyasını değiştirmeniz yeterlidir.

## Bilinmesi gerekenler

- GitHub zamanlanmış görevleri 5–15 dakika gecikebilir.
- Okunamayan bir kaynak olursa uygulamanın üstünde kırmızı uyarı olarak görünür (sitenin RSS adresi değişmiş olabilir).
- Reuters ve AP haberleri Google News üzerinden gelir; bağlantıya tıklayınca önce Google'a, oradan habere yönlendirilirsiniz.
- Herkese açık repolarda 60 gün boyunca hiç işlem yapılmazsa GitHub zamanlanmış görevi durdurabilir. Böyle olursa Actions sekmesinden yeniden etkinleştirin.
