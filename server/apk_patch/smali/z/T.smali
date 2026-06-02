.class public final Lz/T;
.super Ljava/lang/Object;
.source "T.java"


# Логгер сетевого трафика. Пишет в публичную папку Downloads/twwk через
# MediaStore (Android 10+, без разрешений); на старых версиях — в приватный
# каталог приложения.
#   twwk_dump_<ts>.bin : [1 байт dir 'S'/'C'][4 байта BE длина][данные]
#   twwk_msg_<ts>.txt  : разобранные сообщения s=<srcId> op=<opcode> body=<class>


.field public static s:Ljava/io/OutputStream;

.field public static t:Ljava/io/OutputStream;


.method static constructor <clinit>()V
    .locals 1

    const/4 v0, 0x0

    sput-object v0, Lz/T;->s:Ljava/io/OutputStream;

    sput-object v0, Lz/T;->t:Ljava/io/OutputStream;

    return-void
.end method

.method public constructor <init>()V
    .locals 0

    invoke-direct {p0}, Ljava/lang/Object;-><init>()V

    return-void
.end method


# Открыть выходной поток для файла p0 в Downloads/twwk (или приватно).
.method public static open(Ljava/lang/String;)Ljava/io/OutputStream;
    .locals 6

    :try_start_0
    sget-object v0, Lstart/browser/gameTWWK/MiniBrowserActivity;->m:Lstart/browser/gameTWWK/MiniBrowserActivity;

    if-eqz v0, :fail

    sget v1, Landroid/os/Build$VERSION;->SDK_INT:I

    const/16 v2, 0x1d

    if-lt v1, v2, :legacy

    # --- MediaStore (API 29+): Downloads/twwk ---
    invoke-virtual {v0}, Lstart/browser/gameTWWK/MiniBrowserActivity;->getContentResolver()Landroid/content/ContentResolver;

    move-result-object v0

    new-instance v1, Landroid/content/ContentValues;

    invoke-direct {v1}, Landroid/content/ContentValues;-><init>()V

    const-string v2, "_display_name"

    invoke-virtual {v1, v2, p0}, Landroid/content/ContentValues;->put(Ljava/lang/String;Ljava/lang/String;)V

    const-string v2, "mime_type"

    const-string v3, "application/octet-stream"

    invoke-virtual {v1, v2, v3}, Landroid/content/ContentValues;->put(Ljava/lang/String;Ljava/lang/String;)V

    const-string v2, "relative_path"

    const-string v3, "Download/twwk"

    invoke-virtual {v1, v2, v3}, Landroid/content/ContentValues;->put(Ljava/lang/String;Ljava/lang/String;)V

    sget-object v2, Landroid/provider/MediaStore$Downloads;->EXTERNAL_CONTENT_URI:Landroid/net/Uri;

    invoke-virtual {v0, v2, v1}, Landroid/content/ContentResolver;->insert(Landroid/net/Uri;Landroid/content/ContentValues;)Landroid/net/Uri;

    move-result-object v1

    if-eqz v1, :fail

    invoke-virtual {v0, v1}, Landroid/content/ContentResolver;->openOutputStream(Landroid/net/Uri;)Ljava/io/OutputStream;

    move-result-object v0

    return-object v0

    :legacy
    # --- API < 29: приватный внешний каталог ---
    const/4 v1, 0x0

    invoke-virtual {v0, v1}, Lstart/browser/gameTWWK/MiniBrowserActivity;->getExternalFilesDir(Ljava/lang/String;)Ljava/io/File;

    move-result-object v0

    if-eqz v0, :fail

    new-instance v1, Ljava/io/File;

    invoke-direct {v1, v0, p0}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V

    new-instance v0, Ljava/io/FileOutputStream;

    const/4 v2, 0x1

    invoke-direct {v0, v1, v2}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;Z)V

    return-object v0
    :try_end_0
    .catch Ljava/lang/Throwable; {:try_start_0 .. :try_end_0} :catch_0

    :fail
    const/4 v0, 0x0

    return-object v0

    :catch_0
    move-exception v0

    const/4 v0, 0x0

    return-object v0
.end method


# Имя файла с меткой времени: <prefix><millis><suffix>.
.method public static fname(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    .locals 3

    new-instance v0, Ljava/lang/StringBuilder;

    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V

    invoke-virtual {v0, p0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-static {}, Ljava/lang/System;->currentTimeMillis()J

    move-result-wide v1

    invoke-virtual {v0, v1, v2}, Ljava/lang/StringBuilder;->append(J)Ljava/lang/StringBuilder;

    invoke-virtual {v0, p1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v0

    return-object v0
.end method


# Лениво открыть бинарный лог трафика.
.method public static init()V
    .locals 2

    :try_start_0
    sget-object v0, Lz/T;->s:Ljava/io/OutputStream;

    if-nez v0, :done

    const-string v0, "twwk_dump_"

    const-string v1, ".bin"

    invoke-static {v0, v1}, Lz/T;->fname(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;

    move-result-object v0

    invoke-static {v0}, Lz/T;->open(Ljava/lang/String;)Ljava/io/OutputStream;

    move-result-object v0

    sput-object v0, Lz/T;->s:Ljava/io/OutputStream;

    :done
    :try_end_0
    .catch Ljava/lang/Throwable; {:try_start_0 .. :try_end_0} :catch_0

    return-void

    :catch_0
    move-exception v0

    return-void
.end method


# Лениво открыть текстовый лог сообщений.
.method public static tinit()V
    .locals 2

    :try_start_0
    sget-object v0, Lz/T;->t:Ljava/io/OutputStream;

    if-nez v0, :done

    const-string v0, "twwk_msg_"

    const-string v1, ".txt"

    invoke-static {v0, v1}, Lz/T;->fname(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;

    move-result-object v0

    invoke-static {v0}, Lz/T;->open(Ljava/lang/String;)Ljava/io/OutputStream;

    move-result-object v0

    sput-object v0, Lz/T;->t:Ljava/io/OutputStream;

    :done
    :try_end_0
    .catch Ljava/lang/Throwable; {:try_start_0 .. :try_end_0} :catch_0

    return-void

    :catch_0
    move-exception v0

    return-void
.end method


# Записать кусок данных. p0=dir (int 'S'/'C'), p1=buf, p2=off, p3=len.
.method public static w(I[BII)V
    .locals 5

    const-class v0, Lz/T;

    monitor-enter v0

    :try_start_0
    invoke-static {}, Lz/T;->init()V

    sget-object v1, Lz/T;->s:Ljava/io/OutputStream;

    if-eqz v1, :skip

    const/4 v2, 0x5

    new-array v2, v2, [B

    const/4 v3, 0x0

    int-to-byte v4, p0

    aput-byte v4, v2, v3

    const/4 v3, 0x1

    ushr-int/lit8 v4, p3, 0x18

    int-to-byte v4, v4

    aput-byte v4, v2, v3

    const/4 v3, 0x2

    ushr-int/lit8 v4, p3, 0x10

    int-to-byte v4, v4

    aput-byte v4, v2, v3

    const/4 v3, 0x3

    ushr-int/lit8 v4, p3, 0x8

    int-to-byte v4, v4

    aput-byte v4, v2, v3

    const/4 v3, 0x4

    int-to-byte v4, p3

    aput-byte v4, v2, v3

    invoke-virtual {v1, v2}, Ljava/io/OutputStream;->write([B)V

    invoke-virtual {v1, p1, p2, p3}, Ljava/io/OutputStream;->write([BII)V

    invoke-virtual {v1}, Ljava/io/OutputStream;->flush()V

    :skip
    :try_end_0
    .catch Ljava/lang/Throwable; {:try_start_0 .. :try_end_0} :catch_0

    goto :out

    :catch_0
    move-exception v1

    :out
    monitor-exit v0

    return-void
.end method


# Записать разобранное сообщение: p0=srcId, p1=opcode, p2=body.
.method public static msg(IILjava/lang/Object;)V
    .locals 4

    const-class v0, Lz/T;

    monitor-enter v0

    :try_start_0
    invoke-static {}, Lz/T;->tinit()V

    sget-object v1, Lz/T;->t:Ljava/io/OutputStream;

    if-eqz v1, :skip

    new-instance v2, Ljava/lang/StringBuilder;

    invoke-direct {v2}, Ljava/lang/StringBuilder;-><init>()V

    const-string v3, "s="

    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v2, p0}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    const-string v3, " op="

    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v2, p1}, Ljava/lang/StringBuilder;->append(I)Ljava/lang/StringBuilder;

    const-string v3, " body="

    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    if-nez p2, :hasbody

    const-string v3, "null"

    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    goto :nl

    :hasbody
    invoke-virtual {p2}, Ljava/lang/Object;->getClass()Ljava/lang/Class;

    move-result-object v3

    invoke-virtual {v3}, Ljava/lang/Class;->getName()Ljava/lang/String;

    move-result-object v3

    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    :nl
    const-string v3, "\n"

    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;

    invoke-virtual {v2}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;

    move-result-object v2

    invoke-virtual {v2}, Ljava/lang/String;->getBytes()[B

    move-result-object v2

    invoke-virtual {v1, v2}, Ljava/io/OutputStream;->write([B)V

    invoke-virtual {v1}, Ljava/io/OutputStream;->flush()V

    :skip
    :try_end_0
    .catch Ljava/lang/Throwable; {:try_start_0 .. :try_end_0} :catch_0

    goto :out

    :catch_0
    move-exception v1

    :out
    monitor-exit v0

    return-void
.end method


# Обернуть входной поток (данные от сервера).
.method public static in(Ljava/io/InputStream;)Ljava/io/InputStream;
    .locals 1

    new-instance v0, Lz/TI;

    invoke-direct {v0, p0}, Lz/TI;-><init>(Ljava/io/InputStream;)V

    return-object v0
.end method


# Обернуть выходной поток (данные к серверу).
.method public static out(Ljava/io/OutputStream;)Ljava/io/OutputStream;
    .locals 1

    new-instance v0, Lz/TO;

    invoke-direct {v0, p0}, Lz/TO;-><init>(Ljava/io/OutputStream;)V

    return-object v0
.end method
