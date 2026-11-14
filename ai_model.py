import random
from pathlib import Path

import chess
import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

CLASSES = [".", "P", "N", "B", "R", "Q", "K", "p", "n", "b", "r", "q", "k"]
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}

CROP = 64          # working size of one square while building data
INPUT = 48         # network input size
MODEL_PATH = Path(__file__).parent / "models" / "board_cnn.pt"

# Model Architecture
class ChessSquareCNN(nn.Module):
    def __init__(self):
        super().__init__()

        def block(i, o):
            return nn.Sequential(
                nn.Conv2d(i, o, 3, padding=1),
                nn.BatchNorm2d(o),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2),
            )

        # 48 -> 24 -> 12 -> 6
        self.features = nn.Sequential(block(3, 24), block(24, 48), block(48, 96))
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Dropout(0.3),
            nn.Linear(96 * 6 * 6, 128),
            nn.ReLU(inplace=True),
            nn.Linear(128, len(CLASSES)),
        )

    def forward(self, x):
        return self.classifier(self.features(x))

# Image helpers
def split_squares(board_img, size=CROP):
    h, w = board_img.shape[:2]
    ys = np.linspace(0, h, 9).astype(int)
    xs = np.linspace(0, w, 9).astype(int)
    return [
        [
            cv2.resize(board_img[ys[r]:ys[r + 1], xs[c]:xs[c + 1]], (size, size),
                       interpolation=cv2.INTER_AREA)
            for c in range(8)
        ]
        for r in range(8)
    ]


def prep_uint8(crop):
    img = cv2.resize(crop, (INPUT, INPUT), interpolation=cv2.INTER_AREA)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return np.ascontiguousarray(img.transpose(2, 0, 1))


def normalize(batch_uint8):
    return batch_uint8.float() / 127.5 - 1.0


def screen_to_square(row, col, flipped):
    file_idx = 7 - col if flipped else col
    rank_idx = row if flipped else 7 - row
    return chess.square(file_idx, rank_idx)


def grid_to_board(grid, flipped):
    board = chess.Board(None)
    for r in range(8):
        for c in range(8):
            symbol = grid[r][c]
            if symbol != ".":
                board.set_piece_at(screen_to_square(r, c, flipped), chess.Piece.from_symbol(symbol))
    return board


# Inference
class BoardReader:
    def __init__(self):
        self.model = ChessSquareCNN()
        self.model.eval()
        self.ready = False
        self.load()

    def load(self):
        if MODEL_PATH.exists():
            try:
                state = torch.load(MODEL_PATH, map_location="cpu")
                self.model.load_state_dict(state)
                self.model.eval()
                self.ready = True
            except Exception:
                self.ready = False
        return self.ready

    @torch.no_grad()
    def read(self, board_img):
        crops = split_squares(board_img)
        batch = torch.from_numpy(
            np.stack([prep_uint8(crops[r][c]) for r in range(8) for c in range(8)])
        )
        probs = F.softmax(self.model(normalize(batch)), dim=1)
        conf, idx = probs.max(dim=1)
        grid = [[CLASSES[int(idx[r * 8 + c])] for c in range(8)] for r in range(8)]
        return grid, conf.reshape(8, 8).numpy()


def verify_reader(reader, board_img, flipped):
    grid, _ = reader.read(board_img)
    expected = chess.Board()
    correct = 0
    for r in range(8):
        for c in range(8):
            piece = expected.piece_at(screen_to_square(r, c, flipped))
            correct += grid[r][c] == (piece.symbol() if piece else ".")
    return correct

# Self-labelled synthetic data (Enhanced for High Accuracy)
def _piece_alpha(crop):
    k = 6
    corners = np.concatenate([
        crop[:k, :k].reshape(-1, 3), crop[:k, -k:].reshape(-1, 3),
        crop[-k:, :k].reshape(-1, 3), crop[-k:, -k:].reshape(-1, 3),
    ])
    bg = np.median(corners, axis=0)
    diff = np.abs(crop.astype(np.int16) - bg).sum(axis=2)
    mask = (diff > 45).astype(np.uint8)

    grown = cv2.dilate(mask, np.ones((5, 5), np.uint8), iterations=2)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(grown)
    if count <= 1:
        return None
    biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    comp = (labels == biggest).astype(np.uint8)

    contours, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    silhouette = np.zeros_like(comp)
    cv2.drawContours(silhouette, contours, -1, 1, thickness=-1)
    silhouette = cv2.erode(silhouette, np.ones((5, 5), np.uint8), iterations=2)

    if silhouette.mean() < 0.04:
        return None
    return cv2.GaussianBlur(silhouette.astype(np.float32), (3, 3), 0)


def _tint(img):
    if random.random() < 0.4:
        colour = np.array([random.randint(40, 255) for _ in range(3)], np.float32)
        a = random.uniform(0.25, 0.6)
        return (img.astype(np.float32) * (1 - a) + colour * a).astype(np.uint8)
    return img


def _paste(bg, piece, alpha):
    angle = random.uniform(-3, 3)
    scale = random.uniform(0.9, 1.08)
    m = cv2.getRotationMatrix2D((CROP / 2, CROP / 2), angle, scale)
    m[:, 2] += (random.uniform(-3, 3), random.uniform(-3, 3))
    p = cv2.warpAffine(piece, m, (CROP, CROP), borderMode=cv2.BORDER_REPLICATE)
    a = cv2.warpAffine(alpha, m, (CROP, CROP))[..., None]
    return (bg.astype(np.float32) * (1 - a) + p.astype(np.float32) * a).astype(np.uint8)


def _jitter(img):
    img = img.astype(np.float32)
    img = img * random.uniform(0.85, 1.15) + random.uniform(-15, 15)
    img += np.random.normal(0, random.uniform(0, 4), img.shape)
    img = np.clip(img, 0, 255).astype(np.uint8)
    if random.random() < 0.2:
        img = cv2.GaussianBlur(img, (3, 3), 0)
    if random.random() < 0.2:
        overlay = img.copy()
        p1 = (random.randint(0, CROP - 1), random.randint(0, CROP - 1))
        p2 = (random.randint(0, CROP - 1), random.randint(0, CROP - 1))
        cv2.line(overlay, p1, p2, (70, 170, 110), random.randint(5, 10))
        img = cv2.addWeighted(overlay, 0.55, img, 0.45, 0)
    return img


def build_dataset(board_img, flipped, per_class=500):
    crops = split_squares(board_img)
    start = chess.Board()

    backgrounds, pieces = [], {}
    for r in range(8):
        for c in range(8):
            piece = start.piece_at(screen_to_square(r, c, flipped))
            if piece is None:
                backgrounds.append(crops[r][c])
            else:
                alpha = _piece_alpha(crops[r][c])
                if alpha is not None:
                    pieces.setdefault(piece.symbol(), []).append((crops[r][c], alpha))

    missing = [s for s in CLASSES[1:] if s not in pieces]
    if missing or len(backgrounds) < 8:
        raise RuntimeError(
            "Could not isolate every piece type (" + ", ".join(missing) + "). "
            "Make sure the board is in the starting position, the grid is aligned, "
            "and the orientation setting is correct."
        )

    xs, ys = [], []
    for _ in range(per_class):
        img = _jitter(_tint(random.choice(backgrounds)))
        xs.append(prep_uint8(img)); ys.append(0)

    for symbol, items in pieces.items():
        for _ in range(per_class):
            crop, alpha = random.choice(items)
            bg = _tint(random.choice(backgrounds))
            img = _jitter(_paste(bg, crop, alpha))
            xs.append(prep_uint8(img)); ys.append(CLASS_TO_IDX[symbol])

    return torch.from_numpy(np.stack(xs)), torch.tensor(ys, dtype=torch.long)


def train_model(x, y, epochs=25, batch_size=64, progress=None):
    torch.manual_seed(0)
    n = len(x)
    order = torch.randperm(n)
    split = int(n * 0.9)
    train_idx, val_idx = order[:split], order[split:]

    model = ChessSquareCNN()
    optimizer = torch.optim.Adam(model.parameters(), lr=2e-3)
    loss_value, acc = 0.0, 0.0

    for epoch in range(1, epochs + 1):
        model.train()
        shuffled = train_idx[torch.randperm(len(train_idx))]
        for i in range(0, len(shuffled), batch_size):
            idx = shuffled[i:i + batch_size]
            optimizer.zero_grad()
            loss = F.cross_entropy(model(normalize(x[idx])), y[idx])
            loss.backward()
            optimizer.step()
            loss_value = float(loss)

        model.eval()
        with torch.no_grad():
            pred = model(normalize(x[val_idx])).argmax(dim=1)
            acc = float((pred == y[val_idx]).float().mean())
        if progress:
            progress(epoch, epochs, loss_value, acc)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), MODEL_PATH)
    return acc