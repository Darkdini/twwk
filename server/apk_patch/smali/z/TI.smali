.class public Lz/TI;
.super Ljava/io/FilterInputStream;
.source "TI.java"


# Логирующая обёртка InputStream: всё прочитанное от сервера -> dump('S').


.method public constructor <init>(Ljava/io/InputStream;)V
    .locals 0

    invoke-direct {p0, p1}, Ljava/io/FilterInputStream;-><init>(Ljava/io/InputStream;)V

    return-void
.end method


.method public read()I
    .locals 5

    invoke-super {p0}, Ljava/io/FilterInputStream;->read()I

    move-result v0

    if-ltz v0, :ret

    const/4 v1, 0x1

    new-array v1, v1, [B

    const/4 v2, 0x0

    int-to-byte v3, v0

    aput-byte v3, v1, v2

    const/16 v2, 0x53

    const/4 v3, 0x0

    const/4 v4, 0x1

    invoke-static {v2, v1, v3, v4}, Lz/T;->w(I[BII)V

    :ret
    return v0
.end method


.method public read([BII)I
    .locals 1

    invoke-super {p0, p1, p2, p3}, Ljava/io/FilterInputStream;->read([BII)I

    move-result v0

    if-lez v0, :ret

    const/16 v1, 0x53

    invoke-static {v1, p1, p2, v0}, Lz/T;->w(I[BII)V

    :ret
    return v0
.end method
