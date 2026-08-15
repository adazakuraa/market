// ウォッチリスト機能: このブラウザ内(localStorage)にお気に入り銘柄を保存する
// サーバーを持たない静的サイトのため、端末・ブラウザをまたいだ同期はできません。

const WATCHLIST_KEY = 'md_watchlist_tickers';

function getWatchlist() {
  try {
    const raw = localStorage.getItem(WATCHLIST_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    return [];
  }
}

function isWatched(ticker) {
  return getWatchlist().includes(ticker);
}

function toggleWatch(ticker) {
  let list = getWatchlist();
  if (list.includes(ticker)) {
    list = list.filter(t => t !== ticker);
  } else {
    list.push(ticker);
  }
  try {
    localStorage.setItem(WATCHLIST_KEY, JSON.stringify(list));
  } catch (e) {
    // localStorageが使えない環境(プライベートブラウズ等)では何もしない
  }
  return list;
}
