package br.com.trucodamesa;

import java.io.*;
import java.security.SecureRandom;
import java.util.*;

/** Motor local, sem Android, HTTP ou sockets. Mesmas convenções do servidor. */
public final class Game {
    public static final String[] RANKS={"4","5","6","7","Q","J","K","A","2","3"};
    public static final String[] SUITS={"Diamonds","Spades","Hearts","Clubs"};
    public static final String[] SYMBOLS={"♦","♠","♥","♣"};
    public static final int[] STAKES={1,3,6,9,12};
    public static final String[] BOTS={"Você","Bento","Lola","Tião"};
    public static final class Card {
        public int rank,suit;
        public boolean covered;
        public Card(int r,int s){rank=r;suit=s;}
        public String asset(){int[] values={4,5,6,7,12,11,13,1,2,3};return "cards/"+SUITS[suit]+"/"+SUITS[suit]+"_card_"+String.format(Locale.ROOT,"%02d",values[rank])+".png";}
        public String label(){return RANKS[rank]+" "+SYMBOLS[suit];}
    }
    public static final class Play {
        public int seat; public Card card;
        Play(int s,Card c){seat=s;card=c;}
    }
    public int capacity,turn,dealer,stake=1,handNo=0,pendingTeam=-1,pendingValue=0,raiseTeam=-1,eleven=-1,winner=-1;
    public int[] score={0,0};
    public boolean iron=false;
    public String name,phase="playing";
    public final ArrayList<ArrayList<Card>> hands=new ArrayList<>();
    public final ArrayList<Play> table=new ArrayList<>();
    public final ArrayList<Integer> results=new ArrayList<>();
    public final ArrayList<String> log=new ArrayList<>();
    public Card vira;
    public long deadline,botAt;
    private final Random random=new SecureRandom();
    public Game(String n,int c){
        if(c!=2&&c!=4)throw new IllegalArgumentException("Escolha duelo ou duplas.");
        name=n==null||n.trim().isEmpty()?"Você":n.trim();
        if(name.length()>24)name=name.substring(0,24);
        capacity=c;dealer=c-1;deal(System.currentTimeMillis());
    }
    public String player(int seat){return seat==0?name:BOTS[seat];}
    public String team(int seat){return seat%2==0?"Azul":"Coral";}
    public void say(String text){log.add(text);while(log.size()>30)log.remove(0);}
    public void deal(long now){
        ArrayList<Card> deck=new ArrayList<>();
        for(int r=0;r<10;r++)for(int s=0;s<4;s++)deck.add(new Card(r,s));
        Collections.shuffle(deck,random);hands.clear();
        for(int i=0;i<capacity;i++){ArrayList<Card> hand=new ArrayList<>();for(int n=0;n<3;n++)hand.add(deck.remove(deck.size()-1));hands.add(hand);}
        vira=deck.remove(deck.size()-1);table.clear();results.clear();stake=1;pendingTeam=-1;pendingValue=0;raiseTeam=-1;eleven=-1;
        iron=score[0]==11&&score[1]==11;turn=(dealer+1)%capacity;handNo++;phase="playing";
        say("Mão "+handNo+". "+player(turn)+" começa.");
        if(!iron&&(score[0]==11||score[1]==11)){eleven=score[0]==11?0:1;phase="eleven";say("Mão de onze: equipe "+team(eleven)+" decide.");}
        if(iron)say("Mão de ferro! Cartas às cegas, sem aumentos.");
        botAt=now+1100;
    }
    public int power(Card c){if(c.covered)return -1;return c.rank==(vira.rank+1)%10?20+c.suit:c.rank;}
    public static int handWinner(List<Integer> r){
        if(r.size()<2)return -2;
        int a=r.get(0),b=r.get(1);
        if(a>=0&&a==b)return a;
        if(a==-1&&b>=0)return b;
        if(b==-1&&a>=0)return a;
        if(r.size()<3)return -2;
        return r.get(2)>=0?r.get(2):a>=0?a:-1;
    }
    public void award(int team,int points,String reason,long now){
        pendingTeam=-1;pendingValue=0;
        if(team>=0){score[team]+=points;say(reason+" Equipe "+team(team)+" +"+points+".");}else say(reason);
        if(score[0]>=12||score[1]>=12){winner=score[0]>=12?0:1;phase="finished";say("Equipe "+team(winner)+" venceu a partida!");}
        else {phase="hand_end";deadline=now+3200;}
    }
    public boolean canRaise(int seat){return phase.equals("playing")&&turn==seat&&pendingTeam<0&&eleven<0&&!iron&&stake<12&&(raiseTeam<0||raiseTeam==seat%2);}
    private int nextStake(int value){for(int i=0;i<STAKES.length-1;i++)if(STAKES[i]==value)return STAKES[i+1];throw new IllegalArgumentException("A mão já vale doze.");}
    public void raise(int seat,long now){
        if(!canRaise(seat))throw new IllegalArgumentException("Aguarde sua vez para pedir aumento.");
        pendingTeam=seat%2;pendingValue=nextStake(stake);botAt=now+1100;
        say(player(seat)+" pediu "+(pendingValue==3?"TRUCO!":pendingValue+"!"));
    }
    public void respond(int seat,String answer,long now){
        if(phase.equals("eleven")){
            if(seat%2!=eleven)throw new IllegalArgumentException("A decisão é da equipe com onze.");
            if(answer.equals("accept")){stake=3;phase="playing";say("Mão de onze aceita. Vale 3!");}
            else if(answer.equals("run"))award(1-eleven,1,"A equipe com onze correu.",now);
            else throw new IllegalArgumentException("Sem aumentos na mão de onze.");
            botAt=now+1100;return;
        }
        if(!phase.equals("playing")||pendingTeam<0||pendingTeam==seat%2)throw new IllegalArgumentException("Não há pedido para você responder.");
        if(answer.equals("run"))award(pendingTeam,stake,"Pedido recusado.",now);
        else if(answer.equals("accept")){stake=pendingValue;raiseTeam=seat%2;pendingTeam=-1;pendingValue=0;say(player(seat)+" aceitou. Vale "+stake+"!");}
        else if(answer.equals("raise")&&pendingValue<12){stake=pendingValue;pendingTeam=seat%2;pendingValue=nextStake(stake);say(player(seat)+" aumentou para "+pendingValue+"!");}
        else throw new IllegalArgumentException("Resposta inválida.");
        botAt=now+1100;
    }
    public void play(int seat,int index,boolean covered,long now){
        if(!phase.equals("playing")||pendingTeam>=0||turn!=seat)throw new IllegalArgumentException("Aguarde sua vez ou a resposta ao pedido.");
        if(index<0||index>=hands.get(seat).size())throw new IllegalArgumentException("Carta inválida.");
        if(covered&&results.isEmpty())throw new IllegalArgumentException("Não pode cobrir na primeira vaza.");
        Card c=hands.get(seat).remove(index);c.covered=covered;table.add(new Play(seat,c));turn=(seat+1)%capacity;
        if(table.size()==capacity){
            int best=-100,first=-1,winningTeam=-2;boolean tied=false;
            for(Play p:table){int value=power(p.card);if(value>best){best=value;first=p.seat;winningTeam=p.seat%2;tied=false;}else if(value==best&&p.seat%2!=winningTeam)tied=true;}
            int result=tied?-1:winningTeam;results.add(result);turn=first;
            say("Vaza "+results.size()+": "+(result<0?"empatou.":"equipe "+team(result)+" levou."));
            int won=handWinner(results);
            if(won!=-2)award(won,stake,won<0?"Três empates: ninguém pontua.":"Fim da mão.",now);
            else {phase="trick_end";deadline=now+2000;}
        }
        botAt=now+1000;
    }
    public void rematch(long now){if(!phase.equals("finished"))return;score=new int[]{0,0};winner=-1;handNo=0;dealer=(dealer+1)%capacity;deal(now);}
    public void tick(long now){
        if(phase.equals("trick_end")&&now>=deadline){table.clear();phase="playing";botAt=now+650;}
        else if(phase.equals("hand_end")&&now>=deadline){dealer=(dealer+1)%capacity;deal(now);}
        if(now<botAt)return;botAt=now+1100;
        if(phase.equals("eleven")){if(eleven==1)respond(1,"accept",now);return;}
        if(!phase.equals("playing"))return;
        if(pendingTeam>=0){
            if(pendingTeam==0){int power=0;for(Card c:hands.get(1))power=Math.max(power,power(c));respond(1,power>=7||random.nextFloat()<.6?"accept":"run",now);}
            return;
        }
        if(turn==0)return;
        ArrayList<Card> hand=hands.get(turn);
        if(canRaise(turn)){boolean good=false;for(Card c:hand)if(power(c)>=9)good=true;if(good&&random.nextFloat()<.18){raise(turn,now);return;}}
        int selected=0;
        if(iron)selected=random.nextInt(hand.size());
        else {
            for(int i=1;i<hand.size();i++)if(power(hand.get(i))<power(hand.get(selected)))selected=i;
            if(!table.isEmpty()){
                int top=-100;for(Play p:table)top=Math.max(top,power(p.card));
                int beat=-1;for(int i=0;i<hand.size();i++)if(power(hand.get(i))>top&&(beat<0||power(hand.get(i))<power(hand.get(beat))))beat=i;
                if(beat>=0)selected=beat;
            }
        }
        play(turn,selected,false,now);
    }
    public void shiftTimers(long duration){deadline+=duration;botAt+=duration;}
    private static void writeCard(DataOutputStream out,Card c)throws IOException{out.writeInt(c.rank);out.writeInt(c.suit);out.writeBoolean(c.covered);}
    private static Card readCard(DataInputStream in)throws IOException{int r=in.readInt(),s=in.readInt();if(r<0||r>9||s<0||s>3)throw new IOException("Carta inválida");Card c=new Card(r,s);c.covered=in.readBoolean();return c;}
    public void save(OutputStream stream,long now)throws IOException{
        DataOutputStream out=new DataOutputStream(stream);out.writeInt(0x54524331);out.writeUTF(name);out.writeInt(capacity);
        for(int v:new int[]{turn,dealer,stake,handNo,pendingTeam,pendingValue,raiseTeam,eleven,winner,score[0],score[1]})out.writeInt(v);
        out.writeBoolean(iron);out.writeUTF(phase);out.writeLong(Math.max(0,deadline-now));out.writeLong(Math.max(0,botAt-now));writeCard(out,vira);
        for(ArrayList<Card> hand:hands){out.writeInt(hand.size());for(Card c:hand)writeCard(out,c);}
        out.writeInt(table.size());for(Play p:table){out.writeInt(p.seat);writeCard(out,p.card);}
        out.writeInt(results.size());for(int r:results)out.writeInt(r);
        out.writeInt(log.size());for(String line:log)out.writeUTF(line);out.flush();
    }
    private static int count(DataInputStream in,int max)throws IOException{int n=in.readInt();if(n<0||n>max)throw new IOException("Dados de partida inválidos");return n;}
    public static Game load(InputStream stream,long now)throws IOException{
        DataInputStream in=new DataInputStream(stream);if(in.readInt()!=0x54524331)throw new IOException("Versão inválida");
        String name=in.readUTF();int capacity=in.readInt();if(capacity!=2&&capacity!=4)throw new IOException("Mesa inválida");Game g=new Game(name,capacity);
        g.turn=count(in,capacity-1);g.dealer=count(in,capacity-1);g.stake=count(in,12);g.handNo=count(in,100000);
        g.pendingTeam=in.readInt();g.pendingValue=count(in,12);g.raiseTeam=in.readInt();g.eleven=in.readInt();g.winner=in.readInt();g.score[0]=count(in,23);g.score[1]=count(in,23);
        for(int v:new int[]{g.pendingTeam,g.raiseTeam,g.eleven,g.winner})if(v< -1||v>1)throw new IOException("Equipe inválida");
        boolean validStake=false;for(int value:STAKES)if(value==g.stake)validStake=true;if(!validStake)throw new IOException("Valor inválido");
        if(g.pendingTeam>=0&&g.pendingValue!=3&&g.pendingValue!=6&&g.pendingValue!=9&&g.pendingValue!=12)throw new IOException("Pedido inválido");
        g.iron=in.readBoolean();g.phase=in.readUTF();if(!Arrays.asList("playing","trick_end","hand_end","eleven","finished").contains(g.phase))throw new IOException("Estado inválido");
        g.deadline=now+Math.min(4000,Math.max(0,in.readLong()));g.botAt=now+Math.min(1500,Math.max(0,in.readLong()));g.vira=readCard(in);
        g.hands.clear();Set<String> ids=new HashSet<>();ids.add(g.vira.label());
        for(int i=0;i<capacity;i++){int n=count(in,3);ArrayList<Card> hand=new ArrayList<>();for(int k=0;k<n;k++){Card c=readCard(in);if(!ids.add(c.label()))throw new IOException("Cartas repetidas");hand.add(c);}g.hands.add(hand);}
        int n=count(in,capacity);g.table.clear();for(int i=0;i<n;i++){int seat=count(in,capacity-1);Card c=readCard(in);if(!ids.add(c.label()))throw new IOException("Cartas repetidas");g.table.add(new Play(seat,c));}
        g.results.clear();n=count(in,3);for(int i=0;i<n;i++){int r=in.readInt();if(r< -1||r>1)throw new IOException("Vaza inválida");g.results.add(r);}
        g.log.clear();n=count(in,30);for(int i=0;i<n;i++)g.log.add(in.readUTF());return g;
    }
}
