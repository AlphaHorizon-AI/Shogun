param(
    [Parameter(Mandatory = $true)]
    [string]$ImagePath
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object { $_.Name -eq "AsTask" -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 } |
    Select-Object -First 1

function Await-Result {
    param($Operation, [Type]$ResultType)
    $task = $asTaskGeneric.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}

try {
    $storageFileType = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
    $randomStreamType = [Windows.Storage.Streams.IRandomAccessStreamWithContentType, Windows.Storage.Streams, ContentType = WindowsRuntime]
    $bitmapDecoderType = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
    $softwareBitmapType = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
    $bitmapPixelFormatType = [Windows.Graphics.Imaging.BitmapPixelFormat, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
    $bitmapAlphaModeType = [Windows.Graphics.Imaging.BitmapAlphaMode, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
    $ocrEngineType = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
    $ocrResultType = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType = WindowsRuntime]

    $file = Await-Result ($storageFileType::GetFileFromPathAsync($ImagePath)) $storageFileType
    $stream = Await-Result ($file.OpenReadAsync()) $randomStreamType
    try {
        $decoder = Await-Result ($bitmapDecoderType::CreateAsync($stream)) $bitmapDecoderType
        $bitmap = Await-Result (
            $decoder.GetSoftwareBitmapAsync(
                $bitmapPixelFormatType::Bgra8,
                $bitmapAlphaModeType::Premultiplied
            )
        ) $softwareBitmapType
        try {
            $engine = $ocrEngineType::TryCreateFromUserProfileLanguages()
            if ($null -eq $engine) { throw "Windows OCR has no installed recognition language." }
            $recognized = Await-Result ($engine.RecognizeAsync($bitmap)) $ocrResultType
            [ordered]@{
                status = "success"
                engine = "windows-media-ocr"
                language = $engine.RecognizerLanguage.LanguageTag
                text = [string]$recognized.Text
            } | ConvertTo-Json -Depth 3 -Compress
        }
        finally {
            if ($null -ne $bitmap) { $bitmap.Dispose() }
        }
    }
    finally {
        $stream.Dispose()
    }
}
catch {
    [ordered]@{ status = "error"; message = $_.Exception.Message } |
        ConvertTo-Json -Depth 3 -Compress
    exit 2
}
