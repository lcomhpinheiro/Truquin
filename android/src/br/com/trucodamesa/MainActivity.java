package br.com.trucodamesa;

import android.app.*;
import android.os.*;
import android.content.*;
import android.content.res.Configuration;
import android.graphics.*;
import android.graphics.drawable.*;
import android.media.*;
import android.view.*;
import android.widget.*;
import java.io.*;
import java.util.*;
import android.webkit.*;
import android.net.Uri;

/** Interface Android nativa: nenhuma WebView, Python, conexão ou permissão de rede. */
public final class MainActivity extends Activity {
    private final int BG=Color.rgb(244,241,232),INK=Color.rgb(32,59,50),GREEN=Color.rgb(36,91,67),CORAL=Color.rgb(216,121,96),GOLD=Color.rgb(244,210,119);
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final Map<String,Bitmap> bitmaps=new HashMap<>();
    private LinearLayout root,body,hand,actions;
    private TextView status,score,help;
    private BoardView board;
    private Button pauseButton;
    private CheckBox covered;
    private Game game;
    private WebView onlineWeb;
    private boolean playing=false,paused=false,autoPaused=false,fullscreen=true,contrast=false,animations=true,sound=true;
    private long pausedAt=0;
    private float textScale=1;
    private String nickname="Você";
    private SharedPreferences prefs;
    private SoundPool sounds;
    private final Map<String,Integer> soundIds=new HashMap<>();
    private String lastState="";
    private final Runnable ticker=new Runnable(){public void run(){
        if(playing&&game!=null&&!paused){String before=fingerprint();game.tick(System.currentTimeMillis());if(!before.equals(fingerprint())){save();refresh(false);}else if(board!=null&&animations)board.invalidate();}
        handler.postDelayed(this,120);
    }};
    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        prefs=getSharedPreferences("preferences",MODE_PRIVATE);
        fullscreen=prefs.getBoolean("fullscreen",true);contrast=prefs.getBoolean("contrast",false);animations=prefs.getBoolean("animations",true);sound=prefs.getBoolean("sound",true);textScale=prefs.getFloat("textScale",1);nickname=prefs.getString("nickname","Você");
        getWindow().setStatusBarColor(INK);getWindow().setNavigationBarColor(INK);
        setupSound();
        if(state!=null&&state.getBoolean("playing",false)&&load()){playing=true;paused=state.getBoolean("paused",false);if(paused)pausedAt=System.currentTimeMillis();showGame();}else showHome();
        applyFullscreen();handler.post(ticker);
    }
    private int dp(float v){return Math.round(v*getResources().getDisplayMetrics().density);}
    private TextView text(String value,int sp,int color,boolean bold){TextView t=new TextView(this);t.setText(value);t.setTextColor(color);t.setTextSize(sp*textScale);t.setGravity(Gravity.CENTER_VERTICAL);if(bold)t.setTypeface(Typeface.DEFAULT,Typeface.BOLD);return t;}
    private GradientDrawable background(int color,int stroke){GradientDrawable bg=new GradientDrawable();bg.setColor(color);bg.setCornerRadius(dp(6));if(stroke!=0)bg.setStroke(dp(1),stroke);return bg;}
    private Button button(String value,boolean primary,Runnable action){Button b=new Button(this);b.setText(value);b.setAllCaps(false);b.setTextSize(14*textScale);b.setTextColor(primary?Color.WHITE:INK);b.setBackground(background(primary?GREEN:Color.rgb(251,249,240),primary?INK:Color.rgb(187,201,170)));b.setMinHeight(dp(44));b.setPadding(dp(12),dp(4),dp(12),dp(4));b.setOnClickListener(v->action.run());return b;}
    private LinearLayout horizontal(){LinearLayout l=new LinearLayout(this);l.setOrientation(LinearLayout.HORIZONTAL);l.setGravity(Gravity.CENTER_VERTICAL);return l;}
    private void spaced(LinearLayout parent,View child,int width,int height){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(width,height);p.setMargins(dp(4),dp(4),dp(4),dp(4));parent.addView(child,p);}
    private void base(String title){
        root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setBackgroundColor(BG);
        root.setPadding(dp(12),dp(5),dp(12),dp(5));
        root.setOnApplyWindowInsetsListener((view,insets)->{if(Build.VERSION.SDK_INT>=30){android.graphics.Insets bars=insets.getInsets(WindowInsets.Type.systemBars()|WindowInsets.Type.displayCutout());view.setPadding(dp(12)+bars.left,dp(5)+bars.top,dp(12)+bars.right,dp(5)+bars.bottom);}else view.setPadding(dp(12)+insets.getSystemWindowInsetLeft(),dp(5)+insets.getSystemWindowInsetTop(),dp(12)+insets.getSystemWindowInsetRight(),dp(5)+insets.getSystemWindowInsetBottom());return insets;});
        LinearLayout header=horizontal();TextView brand=text("♣  TRUCO DA MESA",16,INK,true);header.addView(brand,new LinearLayout.LayoutParams(0,dp(44),1));
        Button full=button("⛶",false,()->{fullscreen=!fullscreen;prefs.edit().putBoolean("fullscreen",fullscreen).apply();applyFullscreen();});full.setContentDescription("Ativar ou desativar tela cheia");spaced(header,full,dp(43),dp(42));
        Button settings=button("⚙",false,this::showSettings);settings.setContentDescription("Opções de visibilidade, efeitos e regras");spaced(header,settings,dp(43),dp(42));root.addView(header);
        body=new LinearLayout(this);body.setOrientation(LinearLayout.VERTICAL);root.addView(body,new LinearLayout.LayoutParams(-1,0,1));setContentView(root);
    }
    private void showHome(){
        playing=false;if(onlineWeb!=null){onlineWeb.destroy();onlineWeb=null;}base("Truco da Mesa");ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);body.addView(scroll,new LinearLayout.LayoutParams(-1,-1));LinearLayout content=new LinearLayout(this);content.setOrientation(LinearLayout.VERTICAL);content.setPadding(dp(12),dp(12),dp(12),dp(12));scroll.addView(content);
        content.addView(text("SUA MESA. SEU TEMPO.",11,GREEN,true));TextView title=text("A resenha agora\né offline.",34,INK,true);title.setTypeface(Typeface.SERIF,Typeface.NORMAL);spaced(content,title,-1,-2);
        TextView subtitle=text("Jogue em modo avião. As cartas, os bots e a partida ficam no seu celular.",14,contrast?INK:Color.rgb(106,122,95),false);spaced(content,subtitle,-1,-2);
        LinearLayout cards=horizontal();cards.setGravity(Gravity.CENTER);for(int[] c:new int[][]{{9,2},{7,1},{3,3}}){ImageView image=new ImageView(this);image.setImageDrawable(drawable(new Game.Card(c[0],c[1]),false));image.setScaleType(ImageView.ScaleType.FIT_CENTER);spaced(cards,image,dp(65),dp(92));}spaced(content,cards,-1,dp(110));
        EditText name=new EditText(this);name.setText(nickname);name.setHint("Seu apelido");name.setSingleLine(true);name.setTextColor(INK);name.setTextSize(16);name.setFilters(new android.text.InputFilter[]{new android.text.InputFilter.LengthFilter(24)});name.setBackground(background(Color.rgb(252,250,242),Color.rgb(193,205,178)));name.setPadding(dp(12),dp(7),dp(12),dp(7));spaced(content,name,-1,dp(50));
        spaced(content,button("Jogar em duplas  ·  2 × 2",true,()->start(4,name.getText().toString())), -1,dp(50));
        spaced(content,button("Jogar um duelo  ·  1 × 1",false,()->start(2,name.getText().toString())), -1,dp(50));
        Button resume=button("Continuar partida salva  →",false,()->{if(load()){playing=true;paused=false;showGame();}else toast("Não foi possível abrir a partida salva. Comece uma nova.");});resume.setEnabled(new File(getFilesDir(),"partida.bin").isFile());spaced(content,resume,-1,dp(50));
        spaced(content,text("SALVAMENTO AUTOMÁTICO  ·  SEM INTERNET\nCartas pixel art · controles por toque · tela cheia",11,GREEN,false),-1,-2);
        spaced(content,button("Jogar online com amigos",true,this::showOnlineDialog),-1,dp(50));
        spaced(content,button("Como jogar & créditos",false,this::showRules),-1,dp(46));
    }
    private void showOnlineDialog(){
        EditText address=new EditText(this);address.setSingleLine(true);address.setInputType(android.text.InputType.TYPE_CLASS_TEXT|android.text.InputType.TYPE_TEXT_VARIATION_URI);address.setHint("https://seu-servidor ou http://192.168.1.10:8765");address.setText(prefs.getString("server", ""));
        new AlertDialog.Builder(this).setTitle("Multiplayer online").setMessage("Informe o endereço do servidor da turma. Na mesma rede, use o IP do computador. Pela internet, use um servidor ou túnel HTTPS acessível a todos. Depois, crie uma mesa ou entre pelo código.").setView(address).setNegativeButton("Cancelar",null).setPositiveButton("Conectar",(d,w)->{
            String url=address.getText().toString().trim();if(!url.contains("://"))url="http://"+url;
            Uri uri=Uri.parse(url);if(uri.getHost()==null||!("http".equals(uri.getScheme())||"https".equals(uri.getScheme()))){toast("Informe um endereço HTTP ou HTTPS válido.");return;}
            prefs.edit().putString("server",url).apply();showOnline(url);
        }).show();
    }
    private void showOnline(String url){
        playing=false;base("Online");LinearLayout bar=horizontal();
        spaced(bar,button("Início",false,this::showHome),dp(95),dp(44));
        TextView connection=text("ONLINE · servidor da turma",12,GREEN,true);bar.addView(connection,new LinearLayout.LayoutParams(0,dp(44),1));body.addView(bar);
        onlineWeb=new WebView(this);onlineWeb.setBackgroundColor(BG);WebSettings settings=onlineWeb.getSettings();settings.setJavaScriptEnabled(true);settings.setDomStorageEnabled(true);settings.setAllowFileAccess(false);settings.setAllowContentAccess(false);settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        final Uri origin=Uri.parse(url);
        onlineWeb.setWebViewClient(new WebViewClient(){
            @Override public boolean shouldOverrideUrlLoading(WebView view,WebResourceRequest request){Uri target=request.getUrl();return !Objects.equals(origin.getHost(),target.getHost())||!Objects.equals(origin.getScheme(),target.getScheme())||origin.getPort()!=target.getPort();}
            @Override public void onReceivedError(WebView view,WebResourceRequest request,WebResourceError error){if(request.isForMainFrame()){connection.setText("Sem conexão · confira o servidor");toast("Não foi possível conectar. Confira o endereço e mantenha o servidor ligado.");}}
            @Override public void onPageFinished(WebView view,String address){connection.setText("ONLINE · servidor da turma");}
        });
        body.addView(onlineWeb,new LinearLayout.LayoutParams(-1,0,1));onlineWeb.loadUrl(url);applyFullscreen();
    }
    private void start(int capacity,String name){
        Runnable create=()->{nickname=name.trim().isEmpty()?"Você":name.trim();prefs.edit().putString("nickname",nickname).apply();game=new Game(nickname,capacity);paused=false;playing=true;lastState="";save();showGame();};
        if(new File(getFilesDir(),"partida.bin").isFile())new AlertDialog.Builder(this).setTitle("Nova partida").setMessage("Uma nova partida substituirá a partida salva. Começar?").setNegativeButton("Cancelar",null).setPositiveButton("Começar",(d,w)->create.run()).show();else create.run();
    }
    private void showGame(){
        playing=true;base("Partida offline");boolean landscape=getResources().getConfiguration().orientation==Configuration.ORIENTATION_LANDSCAPE;
        LinearLayout gameArea=landscape?horizontal():new LinearLayout(this);if(!landscape)gameArea.setOrientation(LinearLayout.VERTICAL);body.addView(gameArea,new LinearLayout.LayoutParams(-1,-1));
        LinearLayout tableColumn=new LinearLayout(this);tableColumn.setOrientation(LinearLayout.VERTICAL);gameArea.addView(tableColumn,landscape?new LinearLayout.LayoutParams(0,-1,1):new LinearLayout.LayoutParams(-1,0,1));
        score=text("",17,Color.WHITE,true);score.setGravity(Gravity.CENTER);score.setBackgroundColor(INK);score.setPadding(dp(3),dp(8),dp(3),dp(8));tableColumn.addView(score,new LinearLayout.LayoutParams(-1,dp(42)));
        board=new BoardView();tableColumn.addView(board,new LinearLayout.LayoutParams(-1,0,1));
        LinearLayout controls=new LinearLayout(this);controls.setOrientation(LinearLayout.VERTICAL);controls.setPadding(dp(3),dp(4),dp(3),dp(2));gameArea.addView(controls,landscape?new LinearLayout.LayoutParams(dp(330),-1):new LinearLayout.LayoutParams(-1,-2));
        status=text("",14,INK,true);status.setPadding(dp(6),dp(5),dp(6),dp(5));status.setMaxLines(3);status.setMinHeight(dp(43));controls.addView(status,new LinearLayout.LayoutParams(-1,-2));status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        actions=horizontal();actions.setGravity(Gravity.CENTER);controls.addView(actions,new LinearLayout.LayoutParams(-1,dp(48)));
        hand=horizontal();hand.setGravity(Gravity.CENTER);controls.addView(hand,new LinearLayout.LayoutParams(-1,landscape?0:dp(textScale>1?142:128),landscape?1:0));
        help=text("",10,GREEN,false);help.setGravity(Gravity.CENTER);controls.addView(help,new LinearLayout.LayoutParams(-1,dp(24)));
        LinearLayout bottom=horizontal();pauseButton=button(paused?"Continuar":"Pausar",false,this::togglePause);spaced(bottom,pauseButton,0,dp(42));((LinearLayout.LayoutParams)pauseButton.getLayoutParams()).weight=1;
        Button home=button("Início",false,()->{save();showHome();});spaced(bottom,home,0,dp(42));((LinearLayout.LayoutParams)home.getLayoutParams()).weight=1;
        Button history=button("Histórico",false,this::showHistory);spaced(bottom,history,0,dp(42));((LinearLayout.LayoutParams)history.getLayoutParams()).weight=1;controls.addView(bottom);
        lastState="";refresh(true);
    }
    private String fingerprint(){return game==null?"":game.phase+game.turn+game.stake+game.pendingTeam+game.pendingValue+game.handNo+game.table.size()+game.results.toString()+Arrays.toString(game.score)+game.hands.get(0).size();}
    private void action(Runnable command){if(paused)return;try{String previous=game.phase;int cards=game.table.size(),pending=game.pendingValue;command.run();if(game.phase.equals("finished")&&!previous.equals("finished"))playSound("win");else if(game.pendingValue!=pending&&game.pendingValue>0)playSound("raise");else if(game.table.size()>cards)playSound("play");save();refresh(false);}catch(IllegalArgumentException error){toast(error.getMessage());}}
    private void refresh(boolean force){
        if(!playing||game==null||status==null)return;
        String signature=fingerprint()+paused;
        if(!force&&signature.equals(lastState)){board.invalidate();return;}lastState=signature;
        Game g=game;score.setText("AZUL  "+g.score[0]+"     ×     "+g.score[1]+"  CORAL     ·     MÃO "+g.handNo);
        boolean mine=!paused&&g.phase.equals("playing")&&g.pendingTeam<0&&g.turn==0;
        boolean respond=!paused&&(g.phase.equals("eleven")&&g.eleven==0||g.phase.equals("playing")&&g.pendingTeam==1);
        String message;
        if(paused)message="PAUSADO · Sua partida está salva.";
        else if(g.phase.equals("eleven"))message=g.eleven==0?"MÃO DE ONZE · Veja suas cartas e as do parceiro; jogue por 3 ou corra.":"A equipe Coral decide se joga a mão de onze.";
        else if(g.pendingTeam>=0)message="DESAFIO: "+g.pendingValue+" PONTOS! "+(respond?"Aceita, corre ou aumenta?":"Aguardando os adversários…");
        else if(g.phase.equals("finished"))message=g.winner==0?"VITÓRIA! Sua equipe levou a partida.":"Fim da partida. Dessa vez os adversários levaram.";
        else if(!g.phase.equals("playing"))message=g.log.get(g.log.size()-1)+" Próxima mão em instantes…";
        else message=mine?(g.iron?"MÃO DE FERRO · Escolha uma carta às cegas.":"SUA VEZ · Toque em uma carta para jogar."):"É a vez de "+g.player(g.turn)+".";
        if(g.phase.equals("eleven")&&g.eleven==0&&g.capacity==4){StringBuilder partner=new StringBuilder("Parceiro: ");for(Game.Card card:g.hands.get(2))partner.append(card.label()).append("  ");message=partner.toString()+" · Jogar por 3 ou correr?";}
        status.setText(message);status.setTextColor(contrast?Color.rgb(9,29,17):INK);
        actions.removeAllViews();
        if(respond){addAction("Correr",false,()->action(()->g.respond(0,"run",System.currentTimeMillis())));addAction(g.phase.equals("eleven")?"Jogar por 3":"Aceitar",true,()->action(()->g.respond(0,"accept",System.currentTimeMillis())));if(!g.phase.equals("eleven")&&g.pendingValue<12)addAction("Pedir "+nextStake(g.pendingValue),false,()->action(()->g.respond(0,"raise",System.currentTimeMillis())));}
        else if(g.phase.equals("finished")){addAction("Jogar novamente",true,()->action(()->g.rematch(System.currentTimeMillis())));}
        else if(mine){covered=new CheckBox(this);covered.setText("Coberta");covered.setTextColor(INK);covered.setTextSize(13*textScale);covered.setEnabled(!g.results.isEmpty());actions.addView(covered,new LinearLayout.LayoutParams(0,-1,1));if(g.canRaise(0))addAction(g.stake==1?"TRUCO!":"Pedir "+nextStake(g.stake),true,()->action(()->g.raise(0,System.currentTimeMillis())));}
        hand.removeAllViews();int count=g.hands.get(0).size();
        for(int i=0;i<count;i++){final int index=i;ImageButton b=new ImageButton(this);Game.Card c=g.hands.get(0).get(i);b.setImageDrawable(drawable(c,g.iron));b.setScaleType(ImageView.ScaleType.FIT_CENTER);b.setPadding(dp(3),dp(3),dp(3),dp(3));b.setBackground(background(Color.TRANSPARENT,0));b.setEnabled(mine);b.setContentDescription("Jogar carta "+(i+1)+(g.iron?" às cegas":": "+c.label()));b.setOnClickListener(v->action(()->g.play(0,index,covered!=null&&covered.isEnabled()&&covered.isChecked(),System.currentTimeMillis())));LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,-1,1);lp.setMargins(dp(4),dp(2),dp(4),dp(2));hand.addView(b,lp);}
        help.setText(g.iron?"CARTAS ÀS CEGAS · MÃO DE FERRO":"SUA MÃO · SÓ VOCÊ PODE VER ESTAS CARTAS");pauseButton.setText(paused?"Continuar":"Pausar");board.invalidate();
    }
    private int nextStake(int value){for(int i=0;i<Game.STAKES.length-1;i++)if(Game.STAKES[i]==value)return Game.STAKES[i+1];return 12;}
    private void addAction(String title,boolean primary,Runnable command){Button b=button(title,primary,command);LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(0,dp(44),1);lp.setMargins(dp(3),0,dp(3),0);actions.addView(b,lp);}
    private Bitmap bitmap(Game.Card c,boolean back){String path=back?"cards/Backs/back_0.png":c.asset();Bitmap b=bitmaps.get(path);if(b==null){try(InputStream in=getAssets().open(path)){b=BitmapFactory.decodeStream(in);bitmaps.put(path,b);}catch(IOException e){throw new IllegalStateException("Carta ausente no aplicativo: "+path,e);}}return b;}
    private BitmapDrawable drawable(Game.Card c,boolean back){BitmapDrawable d=new BitmapDrawable(getResources(),bitmap(c,back));d.setFilterBitmap(false);d.setAntiAlias(false);return d;}
    private void togglePause(){if(!playing||game==null)return;if(!paused){paused=true;pausedAt=System.currentTimeMillis();save();}else{game.shiftTimers(System.currentTimeMillis()-pausedAt);paused=false;}refresh(true);}
    private void save(){if(game==null)return;File temp=new File(getFilesDir(),"partida.tmp"),file=new File(getFilesDir(),"partida.bin");try(FileOutputStream out=new FileOutputStream(temp)){game.save(out,paused?pausedAt:System.currentTimeMillis());if(!temp.renameTo(file))throw new IOException("Falha na gravação");}catch(IOException e){toast("Não foi possível salvar a partida.");}}
    private boolean load(){File file=new File(getFilesDir(),"partida.bin");if(file.length()>100000)return false;try(FileInputStream in=new FileInputStream(file)){game=Game.load(in,System.currentTimeMillis());return true;}catch(IOException|RuntimeException e){return false;}}
    private void toast(String text){Toast.makeText(this,text,Toast.LENGTH_LONG).show();}
    private void applyFullscreen(){
        if(Build.VERSION.SDK_INT>=30){getWindow().setDecorFitsSystemWindows(false);WindowInsetsController c=getWindow().getInsetsController();if(c!=null){c.setSystemBarsBehavior(WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE);if(fullscreen)c.hide(WindowInsets.Type.systemBars());else c.show(WindowInsets.Type.systemBars());}}
        else getWindow().getDecorView().setSystemUiVisibility(fullscreen?View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY|View.SYSTEM_UI_FLAG_FULLSCREEN|View.SYSTEM_UI_FLAG_HIDE_NAVIGATION|View.SYSTEM_UI_FLAG_LAYOUT_STABLE:View.SYSTEM_UI_FLAG_VISIBLE);
        if(root!=null)root.requestApplyInsets();
    }
    @Override public void onWindowFocusChanged(boolean focus){super.onWindowFocusChanged(focus);if(focus)applyFullscreen();}
    @Override public void onConfigurationChanged(Configuration config){super.onConfigurationChanged(config);if(onlineWeb!=null){applyFullscreen();return;}if(onlineWeb==null){if(playing)showGame();else showHome();}applyFullscreen();}
    @Override protected void onSaveInstanceState(Bundle state){super.onSaveInstanceState(state);save();state.putBoolean("playing",playing);state.putBoolean("paused",paused);}
    @Override protected void onPause(){super.onPause();if(playing&&game!=null&&!paused){autoPaused=true;paused=true;pausedAt=System.currentTimeMillis();save();}}
    @Override protected void onResume(){super.onResume();if(autoPaused&&game!=null){game.shiftTimers(System.currentTimeMillis()-pausedAt);paused=false;autoPaused=false;if(playing)refresh(true);}}
    @Override public void onBackPressed(){if(onlineWeb!=null){showHome();}else if(playing){save();showHome();}else super.onBackPressed();}
    @Override protected void onDestroy(){handler.removeCallbacksAndMessages(null);if(onlineWeb!=null)onlineWeb.destroy();if(sounds!=null)sounds.release();super.onDestroy();}
    private void showSettings(){
        LinearLayout content=new LinearLayout(this);content.setOrientation(LinearLayout.VERTICAL);content.setPadding(dp(22),dp(8),dp(22),dp(10));
        content.addView(text("Tamanho dos textos e cartas",15,INK,true));Spinner size=new Spinner(this);ArrayAdapter<String> adapter=new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,new String[]{"Grande · 100%","Maior · 115%","Extra grande · 130%"});size.setAdapter(adapter);size.setSelection(textScale>=1.3?2:textScale>1?1:0);content.addView(size);
        CheckBox high=new CheckBox(this);high.setText("Alto contraste");high.setChecked(contrast);content.addView(high);
        CheckBox motion=new CheckBox(this);motion.setText("Animações de cartas, truco e vitória");motion.setChecked(animations);content.addView(motion);
        CheckBox audio=new CheckBox(this);audio.setText("Efeitos sonoros");audio.setChecked(sound);content.addView(audio);
        CheckBox full=new CheckBox(this);full.setText("Tela cheia · deslize para ver as barras");full.setChecked(fullscreen);content.addView(full);
        boolean already=paused;if(playing&&!paused)togglePause();
        AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Visibilidade & efeitos").setView(content).setNegativeButton("Cancelar",null).setNeutralButton("Regras",(d,w)->showRules()).setPositiveButton("Aplicar",(d,w)->{
            contrast=high.isChecked();animations=motion.isChecked();sound=audio.isChecked();fullscreen=full.isChecked();textScale=new float[]{1,1.15f,1.3f}[size.getSelectedItemPosition()];prefs.edit().putBoolean("contrast",contrast).putBoolean("animations",animations).putBoolean("sound",sound).putBoolean("fullscreen",fullscreen).putFloat("textScale",textScale).apply();if(onlineWeb==null){if(playing)showGame();else showHome();}applyFullscreen();}).create();
        dialog.setOnDismissListener(d->{if(playing&&!already&&paused)togglePause();});dialog.show();dialog.getButton(AlertDialog.BUTTON_NEUTRAL).setOnClickListener(v->showRules());
    }
    private void showRules(){
        boolean already=paused;if(playing&&!paused)togglePause();
        String rules="OBJETIVO\nChegue a 12 pontos. Três cartas por jogador. Duplas em assentos alternados.\n\nCARTAS\n4 < 5 < 6 < 7 < Q < J < K < A < 2 < 3. A manilha é o valor seguinte à vira (de 3 volta para 4). Manilhas: ♦ < ♠ < ♥ < ♣. Cartas comuns não desempatarão pelo naipe.\n\nVAZAS E EMPATES\nDuas vazas vencem a mão. Se a primeira empata, a próxima com vencedor decide. Se a segunda ou terceira empata, leva quem ganhou a primeira. Três empates: ninguém pontua. Cartas mais altas da mesma dupla não empatam entre si.\n\nTRUCO\nA mão vale 1, depois 3, 6, 9 e 12. Peça na sua vez, antes de jogar. Correr entrega o valor anterior; contra-aumentar aceita o pedido anterior. Quem aceitou pode pedir o próximo aumento.\n\nONZE E FERRO\nCom 11 pontos, confira as cartas do parceiro e decida: jogar por 3 ou correr e dar 1. Em 11 × 11, cartas às cegas. Sem aumentos em ambos os casos.\n\nCOBERTA\nSó a partir da segunda vaza. Perde para toda carta aberta e fica oculta.\n\nCONTROLES\nToque em uma carta para jogar. ⛶ alterna tela cheia. ⚙ ajusta visibilidade e efeitos. A partida é salva automaticamente e pausa quando o app vai para segundo plano.\n\nCRÉDITOS\nCartas: Cards! por SpicyGame, CC0 1.0 (spicygame.itch.io/cards). Referências: Jogatina, Truco Arena e Truco MTJ. Perfil casual sem regra de carta exposta. Todos os assets e regras estão no aplicativo. Modo offline independente da internet. Multiplayer conecta ao servidor informado.";
        TextView view=text(rules,15,INK,false);view.setPadding(dp(22),dp(10),dp(22),dp(10));ScrollView scroll=new ScrollView(this);scroll.addView(view);AlertDialog dialog=new AlertDialog.Builder(this).setTitle("Como jogar & créditos").setView(scroll).setPositiveButton("Entendi",null).create();dialog.setOnDismissListener(d->{if(playing&&!already&&paused)togglePause();});dialog.show();
    }
    private void showHistory(){
        boolean already=paused;if(!paused)togglePause();StringBuilder history=new StringBuilder();
        if(game.eleven==0&&game.capacity==4){history.append("CARTAS DO PARCEIRO\n");for(Game.Card c:game.hands.get(2))history.append(c.label()).append("  ");history.append("\n\n");}
        for(int i=game.log.size()-1;i>=0;i--)history.append(game.log.get(i)).append("\n\n");AlertDialog d=new AlertDialog.Builder(this).setTitle("Na mesa agora").setMessage(history.toString()).setPositiveButton("Voltar",null).create();d.setOnDismissListener(v->{if(!already&&paused)togglePause();});d.show();
    }
    private void setupSound(){try{AudioAttributes attributes=new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_GAME).setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build();sounds=new SoundPool.Builder().setMaxStreams(3).setAudioAttributes(attributes).build();soundIds.put("play",sounds.load(this,R.raw.play,1));soundIds.put("raise",sounds.load(this,R.raw.raise,1));soundIds.put("win",sounds.load(this,R.raw.win,1));}catch(RuntimeException e){sounds=null;}}
    private void playSound(String name){if(sound&&sounds!=null&&soundIds.containsKey(name))sounds.play(soundIds.get(name),.3f,.3f,1,0,1);}

    private final class BoardView extends View {
        private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);
        private String last="";private long changed=0,finished=0;
        BoardView(){super(MainActivity.this);setContentDescription("Mesa de truco, vira e cartas jogadas");setMinimumHeight(dp(180));}
        private void text(Canvas c,String value,float x,float y,float size,int color,boolean bold){p.setColor(color);p.setTypeface(bold?Typeface.create(Typeface.DEFAULT,Typeface.BOLD):Typeface.DEFAULT);p.setTextAlign(Paint.Align.CENTER);p.setTextSize(dp(size)*Math.min(textScale,1.15f));c.drawText(value,x,y,p);}
        private void card(Canvas c,Game.Card value,boolean back,float x,float y,float width,float height){p.setColor(Color.argb(65,0,0,0));c.drawRoundRect(x+dp(2),y+dp(3),x+width+dp(2),y+height+dp(3),dp(3),dp(3),p);p.setFilterBitmap(false);p.setAntiAlias(false);c.drawBitmap(bitmap(value,back),null,new RectF(x,y,x+width,y+height),p);p.setAntiAlias(true);}
        @Override protected void onDraw(Canvas c){super.onDraw(c);if(game==null)return;Game g=game;float w=getWidth(),h=getHeight(),cx=w/2,cy=h/2;long now=SystemClock.uptimeMillis();String sig=fingerprint();if(!sig.equals(last)){last=sig;changed=now;if(g.phase.equals("finished"))finished=now;}
            p.setShader(new LinearGradient(0,0,w,h,contrast?Color.rgb(18,54,39):Color.rgb(47,110,81),Color.rgb(18,58,40),Shader.TileMode.CLAMP));c.drawRoundRect(dp(2),dp(3),w-dp(2),h-dp(3),dp(16),dp(16),p);p.setShader(null);p.setColor(Color.argb(70,191,214,157));p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(dp(1));c.drawRoundRect(dp(15),dp(15),w-dp(15),h-dp(15),dp(55),dp(55),p);p.setStyle(Paint.Style.FILL);
            float seatYTop=dp(32),seatYBottom=h-dp(28);
            for(int seat=0;seat<g.capacity;seat++){float x=cx,y=seat==0?seatYBottom:seatYTop;if(g.capacity==4&&(seat==1||seat==3)){x=seat==1?dp(47):w-dp(47);y=cy;}else if(g.capacity==4&&seat==2)y=seatYTop;
                boolean active=!paused&&g.phase.equals("playing")&&g.pendingTeam<0&&g.turn==seat;int color=seat%2==0?Color.rgb(160,221,240):Color.rgb(255,184,162);
                if(active){p.setColor(Color.argb(animations?(int)(50+25*Math.sin(now/300.0)):65,255,222,137));c.drawRoundRect(x-dp(44),y-dp(22),x+dp(44),y+dp(19),dp(6),dp(6),p);}
                text(c,seat==0?g.name.substring(0,Math.min(g.name.length(),12))+" · você":g.player(seat),x,y,11,Color.WHITE,true);text(c,active?"NA VEZ":seat==0?"SUA EQUIPE":seat%2==0?"PARCEIRO":"ADVERSÁRIO",x,y+dp(15),8,active?GOLD:color,false);
            }
            float cw=Math.min(dp(51),Math.min((w-dp(150))/4.35f,(h-dp(115))*.7f));cw=Math.max(dp(27),cw);float ch=cw*34/27;
            if(g.table.isEmpty())text(c,"♣",cx,cy+dp(12),40,Color.argb(60,198,225,160),true);
            float total=g.table.size()*(cw+dp(5))-dp(5);
            for(int i=0;i<g.table.size();i++){Game.Play play=g.table.get(i);float x=cx-total/2+i*(cw+dp(5)),y=cy-ch/2-dp(4);if(animations&&i==g.table.size()-1){float t=Math.min(1,(now-changed)/650f);float ease=1-(float)Math.pow(1-t,3);y-=(1-ease)*h*.45f;c.save();c.rotate((1-ease)*190,x+cw/2,y+ch/2);card(c,play.card,play.card.covered,x,y,cw,ch);c.restore();}else card(c,play.card,play.card.covered,x,y,cw,ch);}
            for(int i=0;i<3;i++){int value=i<g.results.size()?g.results.get(i):-2;float x=cx+(i-1)*dp(23);p.setColor(value==0?Color.rgb(135,204,230):value==1?CORAL:Color.rgb(30,69,47));c.drawRoundRect(x-dp(9),cy+ch/2+dp(13),x+dp(9),cy+ch/2+dp(31),dp(3),dp(3),p);text(c,value== -1?"=":value== -2?""+(i+1):value==0?"✓":"×",x,cy+ch/2+dp(27),10,value>=0?INK:Color.WHITE,true);}
            float vw=dp(h<dp(220)?27:32),vh=vw*34/27;card(c,g.vira,false,dp(15),h-vh-dp(25),vw,vh);text(c,"VIRA",dp(15)+vw/2,h-vh-dp(30),8,Color.WHITE,true);text(c,"MANILHA: "+Game.RANKS[(g.vira.rank+1)%10],dp(48),h-dp(10),9,GOLD,true);text(c,"VALE "+g.stake,w-dp(45),h-dp(13),11,GOLD,true);
            String banner=null,sub="";
            if(paused){banner="PAUSADO";sub="Seu jogo está salvo";}
            else if(g.pendingTeam>=0){banner=g.pendingValue==3?"TRUCO!":"VALE "+g.pendingValue+"!";sub=g.pendingTeam==1?"Aceita, corre ou aumenta?":"Aguardando os adversários";}
            else if(g.phase.equals("eleven")){banner="MÃO DE ONZE";sub=g.eleven==0?"Jogar por 3 ou correr?":"A equipe Coral está decidindo";}
            else if(g.phase.equals("finished")){banner=g.winner==0?"VITÓRIA!":"FIM DE PARTIDA";sub="Azul "+g.score[0]+" × "+g.score[1]+" Coral";}
            if(banner!=null){if(animations&&g.pendingTeam>=0){float pulse=(float)Math.sin(now/160.0);p.setColor(Color.argb(55,255,210,80));for(int ray=0;ray<12;ray++){c.save();c.rotate(ray*30+now/35f,cx,cy);c.drawRect(cx-dp(3),cy-dp(130),cx+dp(3),cy-dp(45),p);c.restore();}}float bw=Math.min(w-dp(85),dp(290));p.setColor(Color.rgb(13,42,29));c.drawRoundRect(cx-bw/2,cy-dp(39),cx+bw/2,cy+dp(39),dp(8),dp(8),p);p.setColor(GOLD);p.setStyle(Paint.Style.STROKE);p.setStrokeWidth(dp(1.5f));c.drawRoundRect(cx-bw/2,cy-dp(39),cx+bw/2,cy+dp(39),dp(8),dp(8),p);p.setStyle(Paint.Style.FILL);text(c,banner,cx,cy-dp(3),23,GOLD,true);text(c,sub,cx,cy+dp(21),10,Color.WHITE,false);}
            if(animations&&g.phase.equals("finished")&&now-finished<6500){Random r=new Random(23);for(int i=0;i<140;i++){float x=r.nextFloat()*w,y=(r.nextFloat()*h+(now-finished)*.08f)%h;p.setColor(new int[]{GOLD,CORAL,Color.rgb(132,206,230)}[i%3]);c.save();c.rotate((now-finished)/8f+i*23,x,y);c.drawRect(x,y,x+dp(5),y+dp(11),p);c.restore();}}
            if(animations&&!paused)postInvalidateDelayed(40);
        }
    }
}
