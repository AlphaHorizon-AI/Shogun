param(
    [Parameter(Mandatory = $true)]
    [string]$PdfPath,

    [Parameter(Mandatory = $true)]
    [string]$Pages
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding

Add-Type -AssemblyName System.Runtime.WindowsRuntime

$script:AsTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {
        $_.Name -eq "AsTask" -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1
    } |
    Select-Object -First 1
$script:AsTaskAction = [System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {
        $_.Name -eq "AsTask" -and -not $_.IsGenericMethod -and $_.GetParameters().Count -eq 1
    } |
    Select-Object -First 1

function Await-Result {
    param($Operation, [Type]$ResultType)
    $task = $script:AsTaskGeneric.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}

function Await-Action {
    param($Operation)
    $task = $script:AsTaskAction.Invoke($null, @($Operation))
    $task.Wait()
}

try {
    $storageFileType = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
    $pdfDocumentType = [Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType = WindowsRuntime]
    $randomStreamType = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
    $renderOptionsType = [Windows.Data.Pdf.PdfPageRenderOptions, Windows.Data.Pdf, ContentType = WindowsRuntime]
    $bitmapDecoderType = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
    $softwareBitmapType = [Windows.Graphics.Imaging.SoftwareBitmap, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
    $bitmapPixelFormatType = [Windows.Graphics.Imaging.BitmapPixelFormat, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
    $bitmapAlphaModeType = [Windows.Graphics.Imaging.BitmapAlphaMode, Windows.Graphics.Imaging, ContentType = WindowsRuntime]
    $ocrEngineType = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
    $ocrResultType = [Windows.Media.Ocr.OcrResult, Windows.Foundation, ContentType = WindowsRuntime]

    $file = Await-Result ($storageFileType::GetFileFromPathAsync($PdfPath)) $storageFileType
    $document = Await-Result ($pdfDocumentType::LoadFromFileAsync($file)) $pdfDocumentType
    $engine = $ocrEngineType::TryCreateFromUserProfileLanguages()
    if ($null -eq $engine) {
        throw "Windows OCR has no installed recognition language."
    }

    $requestedPages = @(
        $Pages.Split(",") |
            ForEach-Object { [int]$_.Trim() } |
            Where-Object { $_ -ge 1 -and $_ -le $document.PageCount }
    )
    $results = @()
    foreach ($pageNumber in $requestedPages) {
        $page = $document.GetPage([uint32]($pageNumber - 1))
        $stream = [Activator]::CreateInstance($randomStreamType)
        $options = [Activator]::CreateInstance($renderOptionsType)
        $options.DestinationWidth = [uint32][Math]::Max(1, [Math]::Round($page.Dimensions.Width * 2))
        $options.DestinationHeight = [uint32][Math]::Max(1, [Math]::Round($page.Dimensions.Height * 2))

        try {
            Await-Action ($page.RenderToStreamAsync($stream, $options))
            $stream.Seek(0)
            $decoder = Await-Result ($bitmapDecoderType::CreateAsync($stream)) $bitmapDecoderType
            $bitmap = Await-Result (
                $decoder.GetSoftwareBitmapAsync(
                    $bitmapPixelFormatType::Bgra8,
                    $bitmapAlphaModeType::Premultiplied
                )
            ) $softwareBitmapType
            try {
                $recognized = Await-Result ($engine.RecognizeAsync($bitmap)) $ocrResultType
                $results += [ordered]@{ page = $pageNumber; text = [string]$recognized.Text }
            }
            finally {
                if ($null -ne $bitmap) { $bitmap.Dispose() }
            }
        }
        finally {
            $stream.Dispose()
            $page.Dispose()
        }
    }

    [ordered]@{
        status = "success"
        engine = "windows-media-ocr"
        language = $engine.RecognizerLanguage.LanguageTag
        pages = $results
    } | ConvertTo-Json -Depth 4 -Compress
}
catch {
    [ordered]@{
        status = "error"
        message = $_.Exception.Message
    } | ConvertTo-Json -Depth 3 -Compress
    exit 2
}
