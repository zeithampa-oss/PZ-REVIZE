package cz.pzrevize.mobile;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.net.Uri;
import android.util.Base64;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedInputStream;
import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

public final class SyncClient {
    private static final String PREFS="pz_sync";
    private SyncClient(){}

    public interface Callback { void done(Result result); }
    public static final class Result {
        public boolean ok;
        public String message="";
        public int conflicts=0;
        public int imported=0;
        public String transport="";
        public String server="";
    }

    public static SharedPreferences prefs(Context c){return c.getSharedPreferences(PREFS,Context.MODE_PRIVATE);}
    public static boolean configured(Context c){SharedPreferences p=prefs(c);return !p.getString("api_key","").trim().isEmpty() && (!p.getString("lan_url","").trim().isEmpty() || !p.getString("vpn_url","").trim().isEmpty());}
    public static boolean autoSync(Context c){return prefs(c).getBoolean("auto_sync",true);}
    public static String lastSync(Context c){return prefs(c).getString("last_sync","");}
    public static String lastError(Context c){return prefs(c).getString("last_error","");}

    public static void test(Activity a, Callback cb){run(a, null, false, true, cb);}
    public static void sync(Activity a, Db db, boolean pushOnly, Callback cb){run(a, db, pushOnly, false, cb);}

    private static void run(Activity a, Db db, boolean pushOnly, boolean justTest, Callback cb){
        new Thread(() -> {
            Result r=new Result();
            try{
                Endpoint ep=chooseEndpoint(a);
                r.transport=ep.transport; r.server=ep.base;
                if(justTest){JSONObject st=get(ep.base,"/api/mobile/status",ep.key);r.ok=st.optBoolean("ok",true);r.message="Spojení s NAS funguje • "+ep.transport+" • "+st.optString("server","PZ-REVIZE NAS Server");}
                else{
                    JSONObject bundle=SyncStore.exportDirty(db);
                    injectPhotoData(a,bundle.optJSONArray("photos"));
                    JSONObject pushed=post(ep.base,"/api/mobile/push",ep.key,bundle);
                    // The exact exported snapshot is passed back to the store. A row edited
                    // while HTTP is in progress must remain dirty for the next pass.
                    SyncStore.applyPushResult(db,pushed,bundle);
                    r.conflicts=pushed.optJSONArray("conflicts")==null?0:pushed.optJSONArray("conflicts").length();
                    if(!pushOnly){JSONObject remote=get(ep.base,"/api/mobile/bootstrap",ep.key);r.imported=SyncStore.applyBootstrap(db,remote);}
                    r.ok=true;
                    String now=new SimpleDateFormat("dd.MM.yyyy HH:mm:ss",Locale.ROOT).format(new Date());
                    prefs(a).edit().putString("last_sync",now).putString("last_transport",ep.transport).putString("last_error","").apply();
                    r.message="Synchronizace dokončena • "+ep.transport+" • změny v telefonu: "+SyncStore.dirtyCount(db);
                    if(r.conflicts>0)r.message += " • konflikty: "+r.conflicts;
                }
            }catch(Exception e){r.ok=false;r.message=e.getMessage()==null?e.toString():e.getMessage();prefs(a).edit().putString("last_error",r.message).apply();}
            Result out=r; a.runOnUiThread(() -> { if(cb!=null)cb.done(out); });
        },"PZ-Sync").start();
    }

    private static final class Endpoint {String base,key,transport;Endpoint(String b,String k,String t){base=b;key=k;transport=t;}}
    private static Endpoint chooseEndpoint(Context c)throws Exception{
        SharedPreferences p=prefs(c);String key=p.getString("api_key","").trim();if(key.isEmpty())throw new Exception("V nastavení synchronizace není zadaný API klíč.");
        String mode=p.getString("mode","AUTO");String lan=norm(p.getString("lan_url",""));String vpn=norm(p.getString("vpn_url",""));
        List<Endpoint> list=new ArrayList<>();
        if("LAN".equals(mode)){if(!lan.isEmpty())list.add(new Endpoint(lan,key,"LAN"));}
        else if("VPN".equals(mode)){if(!vpn.isEmpty())list.add(new Endpoint(vpn,key,"VPN"));}
        else {if(!lan.isEmpty())list.add(new Endpoint(lan,key,"LAN"));if(!vpn.isEmpty()&&!vpn.equals(lan))list.add(new Endpoint(vpn,key,"VPN"));}
        if(list.isEmpty())throw new Exception("Není zadaná adresa serveru pro LAN ani VPN.");
        StringBuilder errors=new StringBuilder();
        for(Endpoint ep:list){
            try{
                get(ep.base,"/api/mobile/status",ep.key);
                return ep;
            }catch(Exception e){
                String msg=e.getMessage()==null?e.toString():e.getMessage();
                if(msg.contains("HTTP 404")){
                    try{
                        JSONObject legacy=get(ep.base,"/api/status",ep.key);
                        if(legacy.optBoolean("ok",true)){
                            msg="Na NAS běží PZ-REVIZE server, ale bez mobilního API. Aktualizujte NAS server na verzi 0.4.1 nebo novější.";
                        }
                    }catch(Exception ignored){}
                }
                if(errors.length()>0)errors.append(" | ");
                errors.append(ep.transport).append(": ").append(msg);
            }
        }
        throw new Exception("NAS není dostupný pro mobilní synchronizaci. "+errors);
    }
    private static String norm(String x){x=x==null?"":x.trim();while(x.endsWith("/"))x=x.substring(0,x.length()-1);return x;}

    private static JSONObject get(String base,String path,String key)throws Exception{
        HttpURLConnection c=(HttpURLConnection)new URL(base+path).openConnection();c.setConnectTimeout(5000);c.setReadTimeout(20000);c.setRequestMethod("GET");c.setRequestProperty("X-API-Key",key);c.setRequestProperty("Accept","application/json");return read(c);
    }
    private static JSONObject post(String base,String path,String key,JSONObject payload)throws Exception{
        byte[] b=payload.toString().getBytes(StandardCharsets.UTF_8);HttpURLConnection c=(HttpURLConnection)new URL(base+path).openConnection();c.setConnectTimeout(8000);c.setReadTimeout(120000);c.setRequestMethod("POST");c.setDoOutput(true);c.setRequestProperty("X-API-Key",key);c.setRequestProperty("Content-Type","application/json; charset=utf-8");c.setFixedLengthStreamingMode(b.length);try(OutputStream out=c.getOutputStream()){out.write(b);}return read(c);
    }
    private static JSONObject read(HttpURLConnection c)throws Exception{
        int code=c.getResponseCode();InputStream raw=code>=200&&code<300?c.getInputStream():c.getErrorStream();StringBuilder sb=new StringBuilder();if(raw!=null)try(BufferedReader br=new BufferedReader(new InputStreamReader(raw,StandardCharsets.UTF_8))){String line;while((line=br.readLine())!=null)sb.append(line);}c.disconnect();JSONObject o=sb.length()==0?new JSONObject():new JSONObject(sb.toString());if(code<200||code>=300)throw new Exception("HTTP "+code+": "+o.optString("error",o.optString("detail",sb.toString())));return o;
    }

    private static void injectPhotoData(Context c, JSONArray photos)throws Exception{
        if(photos==null)return;
        for(int i=0;i<photos.length();i++){
            JSONObject o=photos.getJSONObject(i);if(o.optLong("server_id")>0)continue;String u=o.optString("uri");if(u.isEmpty())continue;String b64=photoBase64(c,Uri.parse(u));if(!b64.isEmpty()){o.put("data_b64",b64);o.put("data_name","PZ_MOBILE_"+o.optString("uuid")+".jpg");}
        }
    }
    private static String photoBase64(Context c, Uri uri)throws Exception{
        BitmapFactory.Options bounds=new BitmapFactory.Options();bounds.inJustDecodeBounds=true;try(InputStream in=new BufferedInputStream(c.getContentResolver().openInputStream(uri))){BitmapFactory.decodeStream(in,null,bounds);}int max=Math.max(bounds.outWidth,bounds.outHeight);int sample=1;while(max/sample>1800)sample*=2;BitmapFactory.Options opt=new BitmapFactory.Options();opt.inSampleSize=sample;Bitmap bm;try(InputStream in=new BufferedInputStream(c.getContentResolver().openInputStream(uri))){bm=BitmapFactory.decodeStream(in,null,opt);}if(bm==null)return "";int w=bm.getWidth(),h=bm.getHeight();if(Math.max(w,h)>1600){float f=1600f/Math.max(w,h);Bitmap scaled=Bitmap.createScaledBitmap(bm,Math.max(1,Math.round(w*f)),Math.max(1,Math.round(h*f)),true);if(scaled!=bm)bm.recycle();bm=scaled;}ByteArrayOutputStream out=new ByteArrayOutputStream();bm.compress(Bitmap.CompressFormat.JPEG,85,out);bm.recycle();return Base64.encodeToString(out.toByteArray(),Base64.NO_WRAP);
    }
}
