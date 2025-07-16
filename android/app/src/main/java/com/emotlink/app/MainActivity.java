package com.emotlink.app;

import android.os.Bundle;
import android.webkit.*;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        WebView webView = (WebView) findViewById(R.id.webView);

        webView.setWebViewClient(new WebViewClient());
        var webViewSettings = webView.getSettings();
        webViewSettings.setJavaScriptEnabled(true);
        webViewSettings.setUseWideViewPort(true);
        webView.getSettings().setBuiltInZoomControls(false);
        webView.getSettings().setSupportZoom(false);


        webView.loadUrl("http://10.0.2.2:8000"); // localhost
    }

}
