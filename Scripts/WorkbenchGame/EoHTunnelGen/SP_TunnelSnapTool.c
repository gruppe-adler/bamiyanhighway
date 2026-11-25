#ifdef WORKBENCH
//! Hover tool for joining tunnel and cave pieces by their openings (bones/sockets), with a live preview.
//!
//! Pick the tool in the World Editor tool bar ("Entrance Snap (hover)"). Move the cursor over a piece: its free openings light up
//! (yellow). Click the opening of the piece that is to MOVE (cyan), then point at the free opening it should join: green means
//! it fits (same size, a path with a path, a doorframe with a doorway's room side), red means it doesn't and the HUD line says why.
//! While you hover a fitting opening a ghost box shows where the moving piece will end up. Click: the piece is turned and moved so
//! the two openings meet, position and height equal, facing each other (same maths as the generator, SP_TunnelGrower.Attach).
//! One undo step per snap. Esc cancels a pick (or clears the selection when nothing is picked).
//!
//! Drag from one free opening onto another (or shift+click both): a random chain of pieces is built between them
//! (SP_TunnelPathFinder); the two pieces stay where they are. Space: another one.
//!
//! An opening counts as taken when another piece's opening already sits within 0.5 m of it, so pieces that were not selected are
//! known too (unlike the Entrance Snap plugin, which only knows the selection). Pieces are placed yaw-only, like the generator.

//! A catalog piece that stands in the world
class SP_HoverPiece
{
	IEntitySource m_Src;
	SP_TunnelCatalog m_Cat;		// the catalog it belongs to (the TT kit's or the EoH pack's)
	int m_iPiece;		// index in that catalog
	string m_sName;
}

//! One opening of a piece in the world, with where it is right now
class SP_HoverSocket
{
	int m_iWorld;		// index in the tool's piece list
	int m_iSocket;		// index in the piece's catalog sockets
	SP_TunnelSocketDef m_Def;
	vector m_vPos;
	vector m_vDir;
}

//! One piece the menu offers at an opening, and the pose it would get
class SP_MenuEntry
{
	SP_TunnelCatalog m_Cat;
	int m_iPiece;
	int m_iSocket;
	vector m_vPos;
	float m_fYaw;
	bool m_bOverlaps;
	string m_sLabel;
	int m_iGroup;		// the generic kind (normal tunnel, dripstone cave, ...)
	int m_iMove;		// 0 walk, 1 crouch, 2 prone: what the passage is after the piece
	int m_iPlaced;		// how many of this piece stand in the world
	bool m_bSteer;		// a two-opening piece: it has a turn and a length
	float m_fTurn;		// degrees, right positive, from the heading it is joined at
	float m_fAhead;		// metres ahead of the joint to its far opening
}

//! One piece of the catalog that fits the open end, with ALL its sides (the openings it can be joined by, each a pose)
class SP_Asset
{
	SP_TunnelCatalog m_Cat;
	int m_iPiece;
	string m_sName;
	int m_iGroup;		// the generic kind (normal tunnel, dripstone cave, ...)
	int m_iMove;		// walk / crouch / prone after its first side
	int m_iPlaced;
	string m_sGlyph;	// ^ straight, > right, < left, <> both, U u-turn, *N N more exits
	ref array<ref SP_MenuEntry> m_aSides = {};
}

//! Footprint of a piece in the world (a box in plan, with its height range), for the overlap hint in the menu
class SP_HoverFoot
{
	ref array<vector> m_aCorners = {};
	float m_fY0;
	float m_fY1;
}

[WorkbenchToolAttribute(name: "Entrance Snap (hover)", description: "Grow tunnels and caves (the TT kit) from the open ends by keyboard: N picks an open end, Up/Down the type, Left/Right the turn, Space places, X removes. All keys are listed on the strip at the top left.", awesomeFontCode: 0xF0C1)]
class SP_TunnelSnapTool : WorldEditorTool
{
	[Attribute("2.5", UIWidgets.EditBox, "How close, in metres, the cursor ray has to pass to an opening to pick it", category: "Snap")]
	protected float m_fPickRadius;

	[Attribute("0.35", UIWidgets.EditBox, "Radius of the opening markers, metres", category: "Snap")]
	protected float m_fMarkerRadius;

	[Attribute("1", UIWidgets.CheckBox, "Draw a ghost box of the moving piece where it would end up", category: "Snap")]
	protected bool m_bGhost;

	[Attribute("1", UIWidgets.CheckBox, "After placing a piece, go on to the next open end straight away: the new piece's free opening that keeps the heading best, else the nearest other open end. A corridor grows with one key press per piece", category: "Maze")]
	protected bool m_bChain;

	[Attribute("0", UIWidgets.CheckBox, "Hide the pieces that would overlap a placed piece. Off (default): they stay selectable, with a warning. The test uses boxes in plan and height, so curves and rooms give false alarms; key O switches this", category: "Maze")]
	protected bool m_bHideOverlaps;

	[Attribute("1", UIWidgets.CheckBox, "Mark every free opening in the world with a small orange ball, so the open ends of the maze are easy to find", category: "Maze")]
	protected bool m_bFrontier;

	[Attribute("0.12", UIWidgets.EditBox, "Path between two openings: neither piece moves, what the path misses by is spread over its joints. The most one joint may be off, in metres (the step in height: half of it). Smaller is cleaner and found less often", category: "Path")]
	protected float m_fPathGap;

	[Attribute("6000", UIWidgets.EditBox, "Path: how many partial paths are tried before giving up (three attempts). More finds more, and takes longer", category: "Path")]
	protected int m_iPathNodes;

	[Attribute("1", UIWidgets.CheckBox, "Shift+click path: prefer to stay under the ground between the two ends", category: "Path")]
	protected bool m_bPathUnderground;

	protected static const float PATH_MAX_SPAN = 120;
	protected static const float PATH_MAX_WEDGE = 1.5;		// degrees one joint may be off
	protected static const float DRAG_PIXELS = 12;			// moved this far with the button down: a drag, not a click
	protected static const int COL_HOVER = 0xFFFFFF00;
	protected static const int COL_PICK = 0xFF00FFFF;
	protected static const int COL_CANDIDATE = 0x8855FF00;
	protected static const int COL_OK = 0xFF55FF55;
	protected static const int COL_BAD = 0xFFFF4040;
	protected static const int COL_GHOST = 0xFFFF55FF;
	protected static const float OCCUPIED_WITHIN = 0.5;
	protected static const int HOVER_INTERVAL_MS = 30;
	protected static const int REFRESH_INTERVAL_MS = 1500;
	protected static const float CANDIDATE_RANGE = 120;
	protected static const ResourceName GHOST_MATERIAL = "{5E7A9C31D04B82F6}Assets/Tunnels/TT/Data/TT_GhostPreview.emat";
	protected static const int COL_FRONTIER = 0xCCFF2020;
	protected static const float STRIP_X = 20;
	protected static const float STRIP_Y = 88;
	protected static const float STRIP_ROW_H = 19;
	protected static const float STRIP_TEXT = 12;
	protected static const float STRIP_CHAR_W = 7.4;
	protected static const float BOLD_OFFSET = 0.7;		// the text is drawn twice, this far apart: the engine's debug text has no bold
	protected static const float OVERLAP_SHRINK = 0.4;
	protected static const int GROUP_COUNT = 7;

	protected ref array<ref SP_TunnelCatalog> m_aCatalogs = {};
	protected int m_iCatalogKit = -1;
	protected ref array<string> m_aUnknown = {};	// prefabs of our kit's folder that the catalog doesn't know
	protected string m_sNote;
	protected ref map<string, int> m_Cache = new map<string, int>();	// prefab name -> catalog index (or -1)

	protected ref array<ref SP_HoverPiece> m_aWorld = {};
	protected ref array<ref SP_HoverSocket> m_aAll = {};		// every opening of every piece, positions as of the last hover update
	protected ref array<ref SP_HoverSocket> m_aCandidates = {};	// free openings that fit the picked one
	protected int m_iEntityCount = -1;
	protected int m_iLastRefresh;
	protected int m_iLastHover;

	protected ref SCR_DebugShapeManager m_Shapes = new SCR_DebugShapeManager();
	protected ref DebugTextScreenSpace m_Hud;
	protected ref DebugTextScreenSpace m_HudBold;		// the same text again, a hair to the right: bold

	// the picked opening (the piece that will move)
	protected IEntitySource m_PickSrc;
	protected int m_iPickSocket = -1;

	// path between two openings: the first one (shift+click), and what was last built (for "another one")
	protected IEntitySource m_PathStart;
	protected int m_iPathStartSocket = -1;
	protected IEntitySource m_PathFrom;
	protected int m_iPathFromSocket;
	protected IEntitySource m_PathTo;
	protected int m_iPathToSocket;
	protected ref array<IEntitySource> m_aPathMade = {};

	// dragging from an opening
	protected IEntitySource m_DragSrc;
	protected int m_iDragSocket;
	protected float m_fDragX;
	protected float m_fDragY;
	protected bool m_bDragging;

	// the opening under the cursor
	protected int m_iHover = -1;		// index in m_aAll
	protected string m_sHoverKey;		// what was last drawn, so shapes are only rebuilt when it changes
	protected string m_sWhy;			// why the hovered opening doesn't fit ("" = fits or nothing picked)

	protected float m_fYawSign = 1;		// which way the editor turns an entity for a yaw; found out on the first snap
	protected int m_iPressLogged;
	protected int m_iKeysLogged;
	protected bool m_bSignKnown;			// the rotation sign was confirmed by a piece that matched the pose it was given

	// true: placing (an open end gets its piece by keys); false: move a piece that is already placed (click its opening, then the opening it joins)
	protected bool m_bMenuMode = true;

	// the piece being placed at an open end: m_bMenuOpen is true while there is one
	protected bool m_bMenuOpen;
	protected ref array<ref SP_Asset> m_aAssets = {};
	protected ref array<ref DebugTextScreenSpace> m_aRows = {};
	protected ref array<ref SP_HoverFoot> m_aFoot = {};
	protected int m_iAsset;
	protected int m_iSide;
	protected int m_iMenuWorld;			// the piece whose opening the menu is for
	protected int m_iMenuSocket;
	protected SP_TunnelCatalog m_MenuCat;
	protected SP_TunnelSocketDef m_MenuDef;
	protected vector m_vMenuPos;
	protected vector m_vMenuDir;
	protected IEntity m_Ghost;			// the preview of the entry under the cursor (a local entity, not part of the world's data)
	protected ref array<ref SP_HoverSocket> m_aFrontier = {};
	protected string m_sLastAsset;			// the piece placed last, offered first at the next open end
	protected float m_fLastTurn;
	protected int m_iLastMove;
	protected bool m_bTypeOpen;				// the other types are shown on the strip (only while navigating with Up / Down)
	protected int m_iTypeOpenTick;
	protected float m_fChipX;				// layout of the key strip
	protected float m_fChipY;
	protected float m_fChipLimit;
	protected int m_iMenuHidden;			// entries left out because they would overlap
	protected vector m_vLastEnd;			// the open end the camera and the list were last at
	protected bool m_bCycling;				// key N is stepping through the open ends round m_vCycleAnchor
	protected vector m_vCycleAnchor;
	protected int m_iEndCycle;
	protected float m_fMouseX;
	protected float m_fMouseY;
	protected bool m_bCalibLogged;

	//------------------------------------------------------------------------------------------------
	void ~SP_TunnelSnapTool()
	{
		DeleteGhost();
		m_aRows.Clear();
	}

	//------------------------------------------------------------------------------------------------
	protected override void OnActivate()
	{
		EndDrag();
		ForgetPath();
		m_PickSrc = null;
		m_iPickSocket = -1;
		m_iHover = -1;
		m_sHoverKey = "";
		m_iEntityCount = -1;
		m_iLastRefresh = 0;

		// Nothing that needs the world here: after a script reload the editor activates the tool again before its world exists
		// (creating the text here crashed the Workbench). The text, the catalog and the scan come with the first mouse move.
		m_Hud = null;
		m_HudBold = null;
	}

	//------------------------------------------------------------------------------------------------
	//! The on-screen text line, made when there is a world for it
	protected bool EnsureHud()
	{
		if (m_Hud)
			return true;

		if (!m_API)
			return false;

		BaseWorld world = m_API.GetWorld();
		if (!world)
			return false;

		m_Hud = DebugTextScreenSpace.Create(world, "", DebugTextFlags.FACE_CAMERA, 20, 62, 13, 0xFFFFFFFF, 0xE61B1F27);
		m_HudBold = DebugTextScreenSpace.Create(world, "", DebugTextFlags.FACE_CAMERA, 20 + BOLD_OFFSET, 62, 13, 0xFFFFFFFF, 0x00000000);
		return m_Hud != null;
	}

	//------------------------------------------------------------------------------------------------
	protected override void OnDeActivate()
	{
		EndDrag();
		ForgetPath();
		CloseMenu();
		m_Shapes.Clear();
		m_Hud = null;
		m_HudBold = null;
		m_aAll.Clear();
		m_aCandidates.Clear();
	}

	//------------------------------------------------------------------------------------------------
	protected override void OnBeforeUnloadWorld()
	{
		EndDrag();
		ForgetPath();
		CloseMenu();
		m_aWorld.Clear();
		m_aAll.Clear();
		m_aCandidates.Clear();
		m_PickSrc = null;
		m_iEntityCount = -1;
	}

	//------------------------------------------------------------------------------------------------
	protected override void OnLeaveEvent()
	{
		m_iHover = -1;
		Redraw();
	}

	//------------------------------------------------------------------------------------------------
	protected override void OnMousePressEvent(float x, float y, WETMouseButtonFlag buttons)
	{
		int flags = buttons;
		m_fMouseX = x;
		m_fMouseY = y;
		if (m_iPressLogged < 3)
		{
			Print("SP_TunnelSnapTool: mouse press, button flags " + flags.ToString() + " (bit 1 = left button is what picks)");
			m_iPressLogged++;
		}

		if ((flags & 1) == 0)
			return;

		m_iLastHover = 0;
		UpdateHover(x, y);
		if (GetModifierKeyState(ModifierKey.SHIFT))
		{
			if (m_iHover >= 0)
				ShiftClickOpening(m_aAll[m_iHover]);
			else
				SetHud("Path: shift+click a free opening (the balls); Esc cancels");

			return;
		}

		ForgetPath();
		EndDrag();
		if (m_iHover >= 0)
		{
			// a click as ever; held and let go over another opening, it was a drag (see OnMouseReleaseEvent)
			if (m_bMenuMode)
			{
				m_DragSrc = m_aWorld[m_aAll[m_iHover].m_iWorld].m_Src;
				m_iDragSocket = m_aAll[m_iHover].m_iSocket;
				m_fDragX = x;
				m_fDragY = y;
			}

			ClickOpening(m_aAll[m_iHover]);
			return;
		}

		// nothing under the cursor: end the placement or a pick, and select what is there (the default click is replaced while a tool is active)
		if (m_bMenuOpen)
		{
			CloseMenu();
			Redraw();
			ShowHint();
		}

		if (m_PickSrc)
		{
			ClearPick();
			Redraw();
			ShowHint();
		}

		m_API.ClearEntitySelection();
		IEntity entity;
		vector traceStart, traceEnd, traceDir;
		if (!m_API.TraceWorldPos(x, y, TraceFlags.ENTS, traceStart, traceEnd, traceDir, entity))
			return;

		if (!entity)
			return;

		IEntitySource entitySource = m_API.EntityToSource(entity);
		if (entitySource)
			m_API.SetEntitySelection(entitySource);
	}

	//------------------------------------------------------------------------------------------------
	protected override void OnMouseReleaseEvent(float x, float y, WETMouseButtonFlag buttons)
	{
		if (!m_DragSrc)
			return;

		if (!m_bDragging)
		{
			EndDrag();
			return;
		}

		m_iLastHover = 0;
		UpdateHover(x, y);
		SP_HoverSocket from = FindSocket(m_DragSrc, m_iDragSocket);
		EndDrag();
		SP_HoverSocket to;
		if (m_iHover >= 0)
			to = m_aAll[m_iHover];

		if (!from || !to || (from.m_iWorld == to.m_iWorld && from.m_iSocket == to.m_iSocket))
		{
			Redraw();
			ShowHint();
			return;
		}

		StartPath(from, to);
	}

	//------------------------------------------------------------------------------------------------
	protected void EndDrag()
	{
		m_DragSrc = null;
		m_bDragging = false;
	}

	//------------------------------------------------------------------------------------------------
	//! Rebuild a kit's catalog from its prefabs (measures them in the world, like the generator's Rebuild catalog), then rescan
	protected void RebuildKit(int kit)
	{
		ForgetPath();
		CloseMenu();
		ClearPick();
		SP_TunnelCatalog catalog = new SP_TunnelCatalog(kit);
		if (!catalog.Get(m_API, true))
		{
			Print("SP_TunnelSnapTool: rebuilding the catalog of kit " + kit.ToString() + " failed", LogLevel.WARNING);
			return;
		}

		Print(string.Format("SP_TunnelSnapTool: catalog of kit %1 rebuilt: %2 pieces", kit, catalog.m_aPieces.Count()));
		m_aCatalogs.Clear();
		m_iHover = -1;
		m_sHoverKey = "";
		ClearPick();
		if (LoadCatalog())
			RefreshWorld();

		Redraw();
		ShowHint();
	}

	//------------------------------------------------------------------------------------------------
	[ButtonAttribute("Rebuild TT catalog")]
	protected void ButtonRebuildTT()
	{
		RebuildKit(SP_TunnelCatalog.KIT_TT);
	}

	//------------------------------------------------------------------------------------------------
	//! Which catalog piece a source was made from (also when from a child prefab of one): catalog number * 100000 + index, -1 if none
	protected int PieceOfSource(IEntitySource src)
	{
		BaseContainer ancestor = src.GetAncestor();
		if (!ancestor)
			return -1;

		ResourceName keyName = ancestor.GetResourceName();
		string key = keyName;
		int cached;
		if (!key.IsEmpty() && m_Cache.Find(key, cached))
			return cached;

		int found = -1;
		for (int depth = 0; depth < 6 && ancestor && found < 0; depth++)
		{
			ResourceName ancestorName = ancestor.GetResourceName();
			if (!ancestorName.IsEmpty())
			{
				foreach (int c, SP_TunnelCatalog catalog : m_aCatalogs)
				{
					int index = catalog.IndexOfPrefab(ancestorName);
					if (index >= 0)
					{
						found = c * 100000 + index;
						break;
					}
				}
			}

			ancestor = ancestor.GetAncestor();
		}

		// one of ours that the catalog has never measured: say so once
		if (found < 0 && !key.IsEmpty())
		{
			string path = SP_TunnelCatalog.PathOf(keyName);
			if (path.IndexOf("prefabs/tunnels/tt/") == 0 && path.IndexOf("probe") < 0 && m_aUnknown.Find(path) < 0)
				m_aUnknown.Insert(path);
		}

		if (!key.IsEmpty())
			m_Cache.Insert(key, found);

		return found;
	}

	//------------------------------------------------------------------------------------------------
	//! Find the catalog pieces among the world's entities (only when the entity count changed, or on activation)
	protected void RefreshWorld()
	{
		int started = System.GetTickCount();
		m_aWorld.Clear();
		int count = m_API.GetEditorEntityCount();
		m_iEntityCount = count;
		m_iLastRefresh = started;
		for (int i = 0; i < count; i++)
		{
			IEntitySource src = m_API.GetEditorEntity(i);
			if (!src || src.GetParent())
				continue;

			int code = PieceOfSource(src);
			if (code < 0)
				continue;

			SP_HoverPiece piece = new SP_HoverPiece();
			piece.m_Src = src;
			piece.m_Cat = m_aCatalogs[code / 100000];
			piece.m_iPiece = code % 100000;
			piece.m_sName = src.GetName();
			if (piece.m_sName.IsEmpty())
				piece.m_sName = piece.m_Cat.m_aPieces[piece.m_iPiece].m_sName;

			m_aWorld.Insert(piece);
		}

		GatherSockets();
		if (m_PickSrc)
			RebuildCandidates();

		RebuildFrontier();

		m_sNote = "";
		if (!m_aUnknown.IsEmpty())
		{
			m_sNote = string.Format("  [%1 of our prefabs are not in the catalog, e.g. %2: press Rebuild TT catalog in the tool settings]", m_aUnknown.Count(), m_aUnknown[0]);
			Print("SP_TunnelSnapTool:" + m_sNote, LogLevel.WARNING);
		}

		Print(string.Format("SP_TunnelSnapTool: %1 entities scanned, %2 pieces of the catalog, %3 openings, %4 ms", count, m_aWorld.Count(), m_aAll.Count(), System.GetTickCount() - started));
	}

	//------------------------------------------------------------------------------------------------
	//! Every opening of every piece, in world space as the pieces stand now
	protected void GatherSockets()
	{
		m_aAll.Clear();
		foreach (int w, SP_HoverPiece piece : m_aWorld)
		{
			IEntity entity = m_API.SourceToEntity(piece.m_Src);
			if (!entity)
				continue;

			vector mat[4];
			entity.GetWorldTransform(mat);
			float yaw = SP_TunnelGrower.YawOf(mat[2]);
			foreach (int s, SP_TunnelSocketDef def : piece.m_Cat.m_aPieces[piece.m_iPiece].m_aSockets)
			{
				SP_HoverSocket socket = new SP_HoverSocket();
				socket.m_iWorld = w;
				socket.m_iSocket = s;
				socket.m_Def = def;
				socket.m_vPos = mat[3] + SP_TunnelGrower.Rot(def.m_vPos, yaw);
				socket.m_vDir = SP_TunnelGrower.Rot(def.m_vDir, yaw);
				m_aAll.Insert(socket);
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	//! Is another piece's opening already sitting at this one?
	protected bool IsFree(SP_HoverSocket socket)
	{
		foreach (SP_HoverSocket other : m_aAll)
		{
			if (other.m_iWorld == socket.m_iWorld)
				continue;

			if (vector.Distance(other.m_vPos, socket.m_vPos) < OCCUPIED_WITHIN)
				return false;
		}

		return true;
	}

	//------------------------------------------------------------------------------------------------
	//! "" if the two openings can be joined, else the reason
	protected string WhyNot(SP_HoverSocket moverSocket, SP_HoverSocket targetSocket)
	{
		SP_TunnelSocketDef mover = moverSocket.m_Def;
		SP_TunnelSocketDef target = targetSocket.m_Def;
		if (m_aWorld[moverSocket.m_iWorld].m_Cat != m_aWorld[targetSocket.m_iWorld].m_Cat)
			return "different kit (TT and EoH pieces only join within their own kit)";

		return WhyNotDefs(mover, target);
	}

	//------------------------------------------------------------------------------------------------
	protected string WhyNotDefs(SP_TunnelSocketDef mover, SP_TunnelSocketDef target)
	{
		if (mover.m_iSize != target.m_iSize)
			return "different size";

		if (mover.m_iRole == SP_TunnelRole.PATH && target.m_iRole == SP_TunnelRole.PATH)
			return "";

		if (mover.m_iRole == SP_TunnelRole.DOOR && target.m_iRole == SP_TunnelRole.ROOMSIDE)
			return "";

		if (mover.m_iRole == SP_TunnelRole.ROOMSIDE && target.m_iRole == SP_TunnelRole.DOOR)
			return "";

		return "a path joins a path, a doorframe joins a doorway's room side";
	}

	//------------------------------------------------------------------------------------------------
	//! The picked opening as it is now (null if the piece is gone)
	protected SP_HoverSocket PickedSocket()
	{
		if (!m_PickSrc)
			return null;

		foreach (SP_HoverSocket socket : m_aAll)
		{
			if (socket.m_iSocket == m_iPickSocket && m_aWorld[socket.m_iWorld].m_Src == m_PickSrc)
				return socket;
		}

		return null;
	}

	//------------------------------------------------------------------------------------------------
	protected void ClearPick()
	{
		m_PickSrc = null;
		m_iPickSocket = -1;
		m_aCandidates.Clear();
		m_sHoverKey = "";
	}

	//------------------------------------------------------------------------------------------------
	//! Free openings of other pieces that fit the picked one (drawn dim green)
	protected void RebuildCandidates()
	{
		m_aCandidates.Clear();
		SP_HoverSocket picked = PickedSocket();
		if (!picked)
			return;

		foreach (SP_HoverSocket socket : m_aAll)
		{
			if (socket.m_iWorld == picked.m_iWorld)
				continue;

			if (vector.Distance(socket.m_vPos, picked.m_vPos) > CANDIDATE_RANGE)
				continue;

			if (WhyNot(picked, socket) != "")
				continue;

			if (IsFree(socket))
				m_aCandidates.Insert(socket);
		}
	}

	//------------------------------------------------------------------------------------------------
	//! Which free opening is under the cursor (the one the cursor ray passes nearest), and redraw if that changed
	protected void UpdateHover(float x, float y)
	{
		if (m_aCatalogs.IsEmpty() && !LoadCatalog())
			return;

		int now = System.GetTickCount();
		if (m_API.GetEditorEntityCount() != m_iEntityCount && now - m_iLastRefresh > REFRESH_INTERVAL_MS)
			RefreshWorld();
		else
			GatherSockets();

		vector traceStart, traceEnd, traceDir;
		m_API.TraceWorldPos(x, y, TraceFlags.WORLD, traceStart, traceEnd, traceDir);
		vector rayEnd = traceStart + traceDir * 2000;
		float reachSq = m_fPickRadius * m_fPickRadius;

		SP_HoverSocket picked = PickedSocket();
		if (m_PickSrc && !picked)
			ClearPick();

		int best = -1;
		float bestScore = float.INFINITY;
		foreach (int i, SP_HoverSocket socket : m_aAll)
		{
			if (picked && socket.m_iWorld == picked.m_iWorld)
				continue;

			float rayDistSq = Math3D.PointLineSegmentDistanceSqr(socket.m_vPos, traceStart, rayEnd);
			if (rayDistSq > reachSq)
				continue;

			// of two openings the ray passes about equally near, the nearer one to the camera
			float score = Math.Sqrt(rayDistSq) + 0.01 * vector.Distance(traceStart, socket.m_vPos);
			if (score >= bestScore)
				continue;

			if (!IsFree(socket))
				continue;

			best = i;
			bestScore = score;
		}

		m_iHover = best;
		m_sWhy = "";
		string key = "none";
		if (best >= 0)
		{
			SP_HoverSocket hovered = m_aAll[best];
			if (picked)
				m_sWhy = WhyNot(picked, hovered);

			key = string.Format("%1:%2:%3", hovered.m_iWorld, hovered.m_iSocket, m_sWhy);
		}

		if (key == m_sHoverKey)
			return;

		m_sHoverKey = key;
		Redraw();
		ShowHint();
	}

	//------------------------------------------------------------------------------------------------
	protected void ClickOpening(SP_HoverSocket hovered)
	{
		SP_HoverSocket picked = PickedSocket();
		m_bCycling = false;
		if (!picked && m_bMenuMode)
		{
			OpenMenu(hovered);
			return;
		}

		if (!picked)
		{
			// first click: this is the piece that moves
			m_PickSrc = m_aWorld[hovered.m_iWorld].m_Src;
			m_iPickSocket = hovered.m_iSocket;
			RebuildCandidates();
			m_sHoverKey = "";
			m_iHover = -1;
			Redraw();
			ShowHint();
			return;
		}

		if (m_sWhy != "")
		{
			SetHud("Doesn't fit: " + m_sWhy);
			return;
		}

		Snap(picked, hovered);
		ClearPick();
		GatherSockets();
		RebuildFrontier();
		m_iHover = -1;
		Redraw();
	}

	//------------------------------------------------------------------------------------------------
	protected void Snap(SP_HoverSocket mover, SP_HoverSocket target)
	{
		SP_HoverPiece piece = m_aWorld[mover.m_iWorld];
		vector pos;
		float yaw;
		SP_TunnelGrower.Attach(target.m_vPos, target.m_vDir, mover.m_Def, pos, yaw);

		m_API.BeginEntityAction("Entrance snap");
		ApplyPose(piece.m_Src, pos, yaw);
		m_API.EndEntityAction();

		CheckYawSign(piece.m_Src, pos, yaw);

		m_API.SetEntitySelection(piece.m_Src);

		// measure what we got
		string result = "";
		IEntity entity = m_API.SourceToEntity(piece.m_Src);
		if (entity)
		{
			vector mat[4];
			entity.GetWorldTransform(mat);
			float actualYaw = SP_TunnelGrower.YawOf(mat[2]);
			vector now = mat[3] + SP_TunnelGrower.Rot(mover.m_Def.m_vPos, actualYaw);
			float gapCm = vector.Distance(now, target.m_vPos) * 100;
			float facing = SP_TunnelGrower.YawOf(SP_TunnelGrower.Rot(mover.m_Def.m_vDir, actualYaw)) - SP_TunnelGrower.YawOf(target.m_vDir);
			float facingError = Math.AbsFloat(SP_TunnelConnect.Wrap(facing - 180));
			result = string.Format("gap %1 cm, facing off by %2 degrees", gapCm.ToString(-1, 1), facingError.ToString(-1, 1));
		}

		string line = string.Format("%1 opening %2 onto %3 opening %4: %5", piece.m_sName, mover.m_iSocket + 1, m_aWorld[target.m_iWorld].m_sName, target.m_iSocket + 1, result);
		Print("SP_TunnelSnapTool: " + line);
		SetHud("Joined " + line);
	}

	//------------------------------------------------------------------------------------------------
	protected void ApplyPose(IEntitySource src, vector pos, float yaw)
	{
		m_API.SetVariableValue(src, null, "coords", pos.ToString(false));
		m_API.SetVariableValue(src, null, "angleY", (yaw * m_fYawSign).ToString());
	}

	//------------------------------------------------------------------------------------------------
	//! Which way does the editor turn an entity for a yaw? Read it back from the piece just placed. It is only changed when the
	//! piece shows the opposite yaw exactly (a mirror image); a piece that is off for any other reason (a tilted entry, say) says
	//! nothing about the sign. Once a piece has matched, the sign is settled for the session.
	protected void CheckYawSign(IEntitySource src, vector pos, float yaw)
	{
		IEntity entity = m_API.SourceToEntity(src);
		if (!entity)
			return;

		vector mat[4];
		entity.GetWorldTransform(mat);
		float actual = SP_TunnelGrower.YawOf(mat[2]);
		if (Math.AbsFloat(SP_TunnelConnect.Wrap(actual - yaw)) <= 2)
		{
			if (Math.AbsFloat(SP_TunnelConnect.Wrap(yaw)) > 5 && Math.AbsFloat(SP_TunnelConnect.Wrap(yaw)) < 175)
				m_bSignKnown = true;

			return;
		}

		float turned = Math.AbsFloat(SP_TunnelConnect.Wrap(yaw));
		if (m_bSignKnown || turned < 5 || turned > 175 || Math.AbsFloat(SP_TunnelConnect.Wrap(actual + yaw)) > 2)
		{
			Print(string.Format("SP_TunnelSnapTool: the piece stands at yaw %1, not the %2 asked for (tilted prefab? sign known: %3)", Math.Round(actual), Math.Round(yaw), m_bSignKnown), LogLevel.WARNING);
			return;
		}

		m_fYawSign = -m_fYawSign;
		m_bSignKnown = true;
		Print("SP_TunnelSnapTool: the editor turns the other way: redoing the rotation with sign " + m_fYawSign.ToString(), LogLevel.WARNING);
		m_API.BeginEntityAction("Entrance snap (rotation fix)");
		ApplyPose(src, pos, yaw);
		m_API.EndEntityAction();
	}

	//================================================================================================
	// Shift+click path
	//================================================================================================

	//------------------------------------------------------------------------------------------------
	protected void ForgetPath()
	{
		m_PathStart = null;
		m_iPathStartSocket = -1;
		m_PathFrom = null;
		m_PathTo = null;
		m_aPathMade.Clear();
	}

	//------------------------------------------------------------------------------------------------
	//! The first shift+click marks an opening, the second builds the path to it
	protected void ShiftClickOpening(SP_HoverSocket clicked)
	{
		IEntitySource src = m_aWorld[clicked.m_iWorld].m_Src;
		if (!m_PathStart)
		{
			ForgetPath();
			CloseMenu();
			ClearPick();
			m_PathStart = src;
			m_iPathStartSocket = clicked.m_iSocket;
			Redraw();
			ShowHint();
			SetHud(string.Format("Path from %1, opening %2: shift+click the opening it should lead to (Esc cancels)", m_aWorld[clicked.m_iWorld].m_sName, clicked.m_iSocket + 1));
			return;
		}

		if (src == m_PathStart && clicked.m_iSocket == m_iPathStartSocket)
		{
			ForgetPath();
			Redraw();
			ShowHint();
			return;
		}

		SP_HoverSocket first = FindSocket(m_PathStart, m_iPathStartSocket);
		if (!first)
		{
			ForgetPath();
			SetHud("Path: the first piece is gone, shift+click again");
			return;
		}

		StartPath(first, clicked);
	}

	//------------------------------------------------------------------------------------------------
	//! Both openings chosen (by drag or by two shift+clicks): build between them
	protected void StartPath(SP_HoverSocket from, SP_HoverSocket to)
	{
		if (from.m_Def.m_iRole != SP_TunnelRole.PATH || to.m_Def.m_iRole != SP_TunnelRole.PATH)
		{
			SetHud("Path: both openings have to be tunnel openings (not doorframes)");
			return;
		}

		IEntitySource fromSrc = m_aWorld[from.m_iWorld].m_Src;
		IEntitySource toSrc = m_aWorld[to.m_iWorld].m_Src;
		int fromSocket = from.m_iSocket;
		int toSocket = to.m_iSocket;
		CloseMenu();
		ClearPick();
		ForgetPath();
		m_PathFrom = fromSrc;
		m_iPathFromSocket = fromSocket;
		m_PathTo = toSrc;
		m_iPathToSocket = toSocket;
		RunPath(false);
	}

	//------------------------------------------------------------------------------------------------
	protected SP_HoverSocket FindSocket(IEntitySource src, int index)
	{
		foreach (SP_HoverSocket socket : m_aAll)
		{
			if (socket.m_iSocket == index && m_aWorld[socket.m_iWorld].m_Src == src)
				return socket;
		}

		return null;
	}

	//------------------------------------------------------------------------------------------------
	//! What stands in the world, for the path to keep clear of. skip: the pieces of the path about to be replaced
	protected void AddObstacles(SP_TunnelPathFinder finder, notnull array<IEntitySource> skip)
	{
		foreach (SP_HoverPiece piece : m_aWorld)
		{
			if (skip.Find(piece.m_Src) >= 0)
				continue;

			IEntity entity = m_API.SourceToEntity(piece.m_Src);
			if (!entity)
				continue;

			vector mat[4];
			entity.GetWorldTransform(mat);
			float yaw = SP_TunnelGrower.YawOf(mat[2]);
			SP_TunnelPieceDef def = piece.m_Cat.m_aPieces[piece.m_iPiece];
			if (def.m_aSockets.Count() == 2)
			{
				vector a = mat[3] + SP_TunnelGrower.Rot(def.m_aSockets[0].m_vPos, yaw);
				vector b = mat[3] + SP_TunnelGrower.Rot(def.m_aSockets[1].m_vPos, yaw);
				array<vector> points = {};
				points.Insert(a);
				SP_TunnelPathFinder.Along(a, SP_TunnelGrower.Rot(-def.m_aSockets[0].m_vDir, yaw), b, SP_TunnelGrower.Rot(def.m_aSockets[1].m_vDir, yaw), points);
				foreach (vector point : points)
				{
					finder.AddObstaclePoint(point);
				}
			}
			else if (def.m_aSockets.Count() == 1)
			{
				// an entry or a dead end: from its opening back into the piece (the incline's stairs climb)
				vector open = mat[3] + SP_TunnelGrower.Rot(def.m_aSockets[0].m_vPos, yaw);
				vector inward = SP_TunnelGrower.Rot(-def.m_aSockets[0].m_vDir, yaw);
				float climb = 0;
				if (def.m_sName.Contains("Incline"))
					climb = 0.9;

				int depth = 1;
				if (def.m_iKind == SP_TunnelKind.ENTRANCE)
					depth = 5;

				for (int d = 0; d < depth; d++)
				{
					float far = d + 0.5;
					finder.AddObstaclePoint(open + inward * far + Vector(0, climb * far, 0));
				}
			}
			else
			{
				finder.AddObstacleBox(def, mat[3], yaw);
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	//! Search and build. again: replace the path built last by another one
	protected void RunPath(bool again)
	{
		RefreshWorld();
		if (again)
		{
			// all of it still there? (an undo or a delete takes the offer away)
			foreach (IEntitySource made : m_aPathMade)
			{
				if (!FindSocket(made, 0))
				{
					ForgetPath();
					SetHud("Path: the last one has been changed since, shift+click the two openings again");
					return;
				}
			}
		}

		SP_HoverSocket from = FindSocket(m_PathFrom, m_iPathFromSocket);
		SP_HoverSocket to = FindSocket(m_PathTo, m_iPathToSocket);
		if (!from || !to)
		{
			ForgetPath();
			SetHud("Path: one of the two pieces is gone");
			return;
		}

		SP_TunnelSocketDef toDef = to.m_Def;
		vector goal = to.m_vPos;
		vector goalDir = to.m_vDir;
		float span = vector.Distance(from.m_vPos, goal);
		if (span > PATH_MAX_SPAN)
		{
			ForgetPath();
			SetHud(string.Format("Path: the openings are %1 m apart, the most is %2", Math.Round(span), Math.Round(PATH_MAX_SPAN)));
			return;
		}

		float maxGap = Math.Max(m_fPathGap, 0.02);

		SP_TunnelCatalog catalog = m_aWorld[from.m_iWorld].m_Cat;
		string fromName = catalog.m_aPieces[m_aWorld[from.m_iWorld].m_iPiece].m_sName;
		string toName = catalog.m_aPieces[m_aWorld[to.m_iWorld].m_iPiece].m_sName;
		bool caves = SP_TunnelCatalog.ThemeOf(fromName) == SP_TunnelTheme.CAVE && SP_TunnelCatalog.ThemeOf(toName) == SP_TunnelTheme.CAVE;
		WorldEditorAPI depthApi = null;
		if (m_bPathUnderground)
			depthApi = m_API;

		SetHud("Path: searching...");
		int started = System.GetTickCount();
		SP_TunnelPathFinder finder = new SP_TunnelPathFinder(catalog, depthApi, started);
		finder.BuildMoves(caves, from.m_Def.m_iSize != toDef.m_iSize);
		AddObstacles(finder, m_aPathMade);

		bool found = false;
		for (int attempt = 0; attempt < 3 && !found; attempt++)
		{
			found = finder.Find(from.m_vPos, SP_TunnelGrower.YawOf(from.m_vDir), from.m_Def.m_iSize, goal, SP_TunnelGrower.YawOf(-goalDir), toDef.m_iSize, maxGap, maxGap * 0.5, PATH_MAX_WEDGE, m_iPathNodes);
		}

		int took = System.GetTickCount() - started;
		if (!found)
		{
			float rise = goal[1] - from.m_vPos[1];
			string closest = "none";
			if (finder.m_fNearest < 99999)
				closest = finder.m_fNearest.ToString(-1, 2) + " m";

			string failed = string.Format("Path: none found (%1 m apart, %2 m height difference; closest try %3). Try again, or raise the joint gap in the tool settings (Path); short links have few joints to give", Math.Round(span), rise.ToString(-1, 2), closest);
			Print("SP_TunnelSnapTool: " + failed, LogLevel.WARNING);
			SetHud(failed);
			return;
		}

		BuildPath(finder, catalog, again);
		Print(string.Format("SP_TunnelSnapTool: path of %1 pieces from %2 to %3, %4 ms", finder.m_aSteps.Count(), fromName, toName, took));
	}

	//------------------------------------------------------------------------------------------------
	//! Put the found pieces into the world (one undo step); nothing that was there already is touched
	protected void BuildPath(SP_TunnelPathFinder finder, SP_TunnelCatalog catalog, bool again)
	{
		CloseMenu();
		m_API.BeginEntityAction("Entrance snap: path");
		if (again)
		{
			foreach (IEntitySource old : m_aPathMade)
			{
				m_API.DeleteEntity(old);
			}
		}

		m_aPathMade.Clear();
		array<vector> positions = {};
		array<float> yaws = {};
		int layer = m_API.GetCurrentEntityLayerId();
		foreach (SP_PathStep step : finder.m_aSteps)
		{
			SP_TunnelPieceDef def = catalog.m_aPieces[step.m_iPiece];
			IEntitySource src = m_API.CreateEntity(def.m_sPrefab, "", layer, null, step.m_vPos, Vector(0, step.m_fYaw * m_fYawSign, 0));
			if (!src)
			{
				Print("SP_TunnelSnapTool: CreateEntity failed for " + def.m_sPrefab, LogLevel.WARNING);
				continue;
			}

			m_aPathMade.Insert(src);
			positions.Insert(step.m_vPos);
			yaws.Insert(step.m_fYaw);
		}

		m_API.EndEntityAction();

		// the editor's turning direction, if this session hasn't settled it yet: settle it on one piece, then redo the others
		if (!m_bSignKnown)
		{
			foreach (int c, IEntitySource check : m_aPathMade)
			{
				float turned = Math.AbsFloat(SP_TunnelConnect.Wrap(yaws[c]));
				if (turned > 5 && turned < 175)
				{
					float sign = m_fYawSign;
					CheckYawSign(check, positions[c], yaws[c]);
					if (sign != m_fYawSign)
					{
						m_API.BeginEntityAction("Entrance snap: path (rotation fix)");
						foreach (int r, IEntitySource redo : m_aPathMade)
						{
							ApplyPose(redo, positions[r], yaws[r]);
						}

						m_API.EndEntityAction();
					}

					break;
				}
			}
		}

		// the whole path selected, so X removes it
		m_API.ClearEntitySelection();
		foreach (int s, IEntitySource selected : m_aPathMade)
		{
			if (s == 0)
				m_API.SetEntitySelection(selected);
			else
				m_API.AddToEntitySelection(selected);
		}

		RefreshWorld();
		m_iHover = -1;
		m_sHoverKey = "";
		Redraw();
		DrawMenu();
		float gapCm = finder.m_fGapFlat * 100;
		float stepCm = finder.m_fGapHeight * 100;
		float wedge = Math.AbsFloat(finder.m_fGapYaw);
		string joints = string.Format("each joint off by %1 cm, step %2 cm, %3 deg", gapCm.ToString(-1, 0), stepCm.ToString(-1, 0), wedge.ToString(-1, 1));
		Print("SP_TunnelSnapTool: " + joints);
		SetHud(string.Format("Path: %1 pieces, %2 m, %3.  Space: another one, X: remove it", m_aPathMade.Count(), Math.Round(finder.m_fLength), joints));
	}

	//------------------------------------------------------------------------------------------------
	protected void SetHud(string text)
	{
		if (!EnsureHud())
			return;

		m_Hud.SetText(" " + text + " ");
		if (m_HudBold)
			m_HudBold.SetText(" " + text + " ");
	}

	//------------------------------------------------------------------------------------------------
	protected void Redraw()
	{
		m_Shapes.Clear();
		ShapeFlags flags = ShapeFlags.NOOUTLINE | ShapeFlags.NOZBUFFER;
		SP_HoverSocket picked = PickedSocket();
		if (m_bFrontier)
		{
			int shown = 0;
			foreach (SP_HoverSocket open : m_aFrontier)
			{
				if (shown > 400)
					break;

				shown++;
				m_Shapes.AddSphere(open.m_vPos, m_fMarkerRadius * 0.8, COL_FRONTIER, flags);
			}
		}

		if (m_PathStart)
		{
			foreach (SP_HoverSocket first : m_aAll)
			{
				if (first.m_iSocket != m_iPathStartSocket || m_aWorld[first.m_iWorld].m_Src != m_PathStart)
					continue;

				m_Shapes.AddSphere(first.m_vPos, m_fMarkerRadius * 1.5, COL_GHOST, flags);
				m_Shapes.AddArrow(first.m_vPos, first.m_vPos + first.m_vDir * 2, 0, COL_GHOST, flags);
			}
		}

		if (m_bDragging)
		{
			SP_HoverSocket dragged = FindSocket(m_DragSrc, m_iDragSocket);
			if (dragged)
			{
				m_Shapes.AddSphere(dragged.m_vPos, m_fMarkerRadius * 1.5, COL_GHOST, flags);
				if (m_iHover >= 0)
					m_Shapes.AddLine(dragged.m_vPos, m_aAll[m_iHover].m_vPos, COL_GHOST, flags);
			}
		}

		if (m_bMenuOpen)
		{
			m_Shapes.AddSphere(m_vMenuPos, m_fMarkerRadius * 1.3, COL_PICK, flags);
			m_Shapes.AddArrow(m_vMenuPos, m_vMenuPos + m_vMenuDir * 2, 0, COL_PICK, flags);
		}

		if (picked)
		{
			foreach (SP_HoverSocket candidate : m_aCandidates)
			{
				m_Shapes.AddSphere(candidate.m_vPos, m_fMarkerRadius * 0.7, COL_CANDIDATE, flags);
			}

			m_Shapes.AddSphere(picked.m_vPos, m_fMarkerRadius * 1.3, COL_PICK, flags);
			m_Shapes.AddArrow(picked.m_vPos, picked.m_vPos + picked.m_vDir * 2, 0, COL_PICK, flags);
		}

		if (m_iHover < 0)
			return;

		SP_HoverSocket hovered = m_aAll[m_iHover];
		int colour = COL_HOVER;
		if (picked)
		{
			colour = COL_OK;
			if (m_sWhy != "")
				colour = COL_BAD;
		}

		m_Shapes.AddSphere(hovered.m_vPos, m_fMarkerRadius * 1.3, colour, flags);
		m_Shapes.AddArrow(hovered.m_vPos, hovered.m_vPos + hovered.m_vDir * 2, 0, colour, flags);
		if (!picked || m_sWhy != "")
			return;

		// the preview: the moving piece where it will stand
		vector pos;
		float yaw;
		SP_TunnelGrower.Attach(hovered.m_vPos, hovered.m_vDir, picked.m_Def, pos, yaw);
		m_Shapes.AddLine(picked.m_vPos, hovered.m_vPos, COL_GHOST, flags);
		if (!m_bGhost)
			return;

		SP_HoverPiece pickedPiece = m_aWorld[picked.m_iWorld];
		SP_TunnelPieceDef def = pickedPiece.m_Cat.m_aPieces[pickedPiece.m_iPiece];
		array<vector> corner = {};
		for (int i = 0; i < 8; i++)
		{
			vector local = Vector(def.m_vMin[0], def.m_vMin[1], def.m_vMin[2]);
			if (i & 1)
				local[0] = def.m_vMax[0];

			if (i & 2)
				local[1] = def.m_vMax[1];

			if (i & 4)
				local[2] = def.m_vMax[2];

			corner.Insert(pos + SP_TunnelGrower.Rot(local, yaw));
		}

		for (int j = 0; j < 8; j++)
		{
			for (int bit = 1; bit <= 4; bit *= 2)
			{
				if ((j & bit) == 0)
					m_Shapes.AddLine(corner[j], corner[j | bit], COL_GHOST, flags);
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	//! Every free opening in the world (drawn as small balls, and what a corridor can still grow from)
	protected void RebuildFrontier()
	{
		m_aFrontier.Clear();
		foreach (SP_HoverSocket socket : m_aAll)
		{
			if (IsFree(socket))
				m_aFrontier.Insert(socket);
		}
	}

	//------------------------------------------------------------------------------------------------
	protected bool Fits(SP_TunnelSocketDef a, SP_TunnelSocketDef b)
	{
		return WhyNotDefs(a, b) == "";
	}

	//------------------------------------------------------------------------------------------------
	//! Same place and same way up, from either end? (a straight piece, joined by its other opening)
	protected bool SamePlacement(SP_TunnelPieceDef def, vector posA, float yawA, vector posB, float yawB)
	{
		if (def.m_aSockets.Count() != 2)
			return false;

		vector centre = (def.m_vMin + def.m_vMax) * 0.5;
		vector a = posA + SP_TunnelGrower.Rot(centre, yawA);
		vector b = posB + SP_TunnelGrower.Rot(centre, yawB);
		if (vector.Distance(a, b) > 0.25)
			return false;

		float diff = Math.AbsFloat(SP_TunnelConnect.Wrap(yawA - yawB));
		return diff < 2 || Math.AbsFloat(diff - 180) < 2;
	}

	//------------------------------------------------------------------------------------------------
	//! The box of a piece in plan (four corners, smaller by shrink on every side) and its height range
	protected SP_HoverFoot Footprint(SP_TunnelPieceDef def, vector pos, float yaw)
	{
		float x0 = def.m_vMin[0] + OVERLAP_SHRINK;
		float x1 = def.m_vMax[0] - OVERLAP_SHRINK;
		float z0 = def.m_vMin[2] + OVERLAP_SHRINK;
		float z1 = def.m_vMax[2] - OVERLAP_SHRINK;
		float low = def.m_vMin[1];
		float high = def.m_vMax[1];
		if (def.m_iKind == SP_TunnelKind.ENTRANCE && !def.m_sName.Contains("Incline"))
		{
			// the rock mound round a horizontal entry is not tunnel: only the middle counts
			x0 = Math.Max(x0, -1.2);
			x1 = Math.Min(x1, 1.2);
			low = Math.Max(low, -0.9);
			high = Math.Min(high, 3.0);
		}

		if (x1 < x0)
		{
			x0 = (x0 + x1) * 0.5;
			x1 = x0;
		}

		if (z1 < z0)
		{
			z0 = (z0 + z1) * 0.5;
			z1 = z0;
		}

		SP_HoverFoot foot = new SP_HoverFoot();
		foot.m_aCorners.Insert(pos + SP_TunnelGrower.Rot(Vector(x0, 0, z0), yaw));
		foot.m_aCorners.Insert(pos + SP_TunnelGrower.Rot(Vector(x1, 0, z0), yaw));
		foot.m_aCorners.Insert(pos + SP_TunnelGrower.Rot(Vector(x1, 0, z1), yaw));
		foot.m_aCorners.Insert(pos + SP_TunnelGrower.Rot(Vector(x0, 0, z1), yaw));
		foot.m_fY0 = pos[1] + low + OVERLAP_SHRINK;
		foot.m_fY1 = pos[1] + high - OVERLAP_SHRINK;
		return foot;
	}

	//------------------------------------------------------------------------------------------------
	//! Do two boxes in plan overlap? (separating axis test on the edges of both)
	protected bool QuadsOverlap(notnull array<vector> a, notnull array<vector> b)
	{
		for (int pass = 0; pass < 2; pass++)
		{
			array<vector> quad = a;
			if (pass == 1)
				quad = b;

			for (int i = 0; i < 4; i++)
			{
				vector edge = quad[(i + 1) % 4] - quad[i];
				float nx = -edge[2];
				float nz = edge[0];
				if (nx == 0 && nz == 0)
					continue;

				float minA = 1000000;
				float maxA = -1000000;
				float minB = 1000000;
				float maxB = -1000000;
				for (int k = 0; k < 4; k++)
				{
					float da = a[k][0] * nx + a[k][2] * nz;
					float db = b[k][0] * nx + b[k][2] * nz;
					minA = Math.Min(minA, da);
					maxA = Math.Max(maxA, da);
					minB = Math.Min(minB, db);
					maxB = Math.Max(maxB, db);
				}

				if (maxA < minB || maxB < minA)
					return false;
			}
		}

		return true;
	}

	//------------------------------------------------------------------------------------------------
	protected void DeleteGhost()
	{
		if (!m_Ghost)
			return;

		delete m_Ghost;
		m_Ghost = null;
	}

	//------------------------------------------------------------------------------------------------
	//! The selected entry as a see-through copy in the world (a local entity with the ghost material, gone again when the
	//! selection changes or the menu closes). If the prefab can't be spawned, the box of the piece is drawn instead.
	protected void ShowGhost()
	{
		DeleteGhost();
		SP_MenuEntry entry = SelectedEntry();
		if (!entry)
			return;

		ResourceName prefab = entry.m_Cat.m_aPieces[entry.m_iPiece].m_sPrefab;
		Resource resource = Resource.Load(prefab);
		ArmaReforgerScripted game = GetGame();
		if (!resource || !resource.IsValid() || !game)
			return;

		EntitySpawnParams params = new EntitySpawnParams();
		params.TransformMode = ETransformMode.WORLD;
		params.Transform[0] = SP_TunnelGrower.Rot("1 0 0", entry.m_fYaw);
		params.Transform[1] = "0 1 0";
		params.Transform[2] = SP_TunnelGrower.Rot("0 0 1", entry.m_fYaw);
		params.Transform[3] = entry.m_vPos;
		m_Ghost = game.SpawnEntityPrefabLocal(resource, m_API.GetWorld(), params);
		if (m_Ghost)
			SCR_Global.SetMaterial(m_Ghost, GHOST_MATERIAL, true);
	}

	//------------------------------------------------------------------------------------------------
	//! Place the selected entry for real (one undo step), select it, and carry on from its far opening when there is just one
	protected void PlaceSelected()
	{
		SP_MenuEntry entry = SelectedEntry();
		if (!entry)
			return;

		SP_TunnelPieceDef def = entry.m_Cat.m_aPieces[entry.m_iPiece];
		string targetName = m_aWorld[m_iMenuWorld].m_sName;
		int targetSocket = m_iMenuSocket;
		vector heading = m_vMenuDir;
		vector fromPos = m_vMenuPos;
		CloseMenu();

		m_API.BeginEntityAction("Entrance snap: add piece");
		IEntitySource src = m_API.CreateEntity(def.m_sPrefab, "", m_API.GetCurrentEntityLayerId(), null, entry.m_vPos, Vector(0, entry.m_fYaw * m_fYawSign, 0));
		m_API.EndEntityAction();
		if (!src)
		{
			SetHud("Could not create " + def.m_sName);
			Print("SP_TunnelSnapTool: CreateEntity failed for " + def.m_sPrefab, LogLevel.WARNING);
			Redraw();
			return;
		}

		CheckYawSign(src, entry.m_vPos, entry.m_fYaw);
		m_API.SetEntitySelection(src);
		m_sLastAsset = def.m_sName;
		m_fLastTurn = entry.m_fTurn;
		m_iLastMove = entry.m_iMove;
		Print(string.Format("SP_TunnelSnapTool: placed %1 (opening %2) onto %3 opening %4", def.m_sName, entry.m_iSocket + 1, targetName, targetSocket + 1));

		// take the new piece into the picture, then see what is left open on it
		RefreshWorld();
		int added = -1;
		foreach (int w, SP_HoverPiece piece : m_aWorld)
		{
			if (piece.m_Src == src)
				added = w;
		}

		array<SP_HoverSocket> open = {};
		foreach (SP_HoverSocket socket : m_aAll)
		{
			if (socket.m_iWorld == added && IsFree(socket))
				open.Insert(socket);
		}

		m_iHover = -1;
		m_sHoverKey = "";
		m_bCycling = false;
		SP_HoverSocket next = NextEndAfter(added, heading, fromPos);
		if (!next)
		{
			Redraw();
			SetHud("Placed " + def.m_sName + ": no free opening left anywhere");
			return;
		}

		if (m_bChain)
		{
			OpenMenu(next);
			return;
		}

		m_vLastEnd = next.m_vPos;
		Redraw();
		SetHud(string.Format("Placed %1 (%2 free openings on it). Next open end: %3, opening %4: click it, or N for another", def.m_sName, open.Count(), m_aWorld[next.m_iWorld].m_sName, next.m_iSocket + 1));
	}

	//------------------------------------------------------------------------------------------------
	//! What a two-opening piece does from the opening it is joined by: its length ahead, the turn, the climb
	protected string Describe(SP_MenuEntry entry, SP_TunnelSocketDef farSocket, vector pos, float yaw)
	{
		vector farPos = pos + SP_TunnelGrower.Rot(farSocket.m_vPos, yaw);
		vector farDir = SP_TunnelGrower.Rot(farSocket.m_vDir, yaw);
		vector right = Vector(m_vMenuDir[2], 0, -m_vMenuDir[0]);
		float along = vector.Dot(farPos - m_vMenuPos, m_vMenuDir);
		float turn = Math.AbsFloat(SP_TunnelConnect.Wrap(SP_TunnelGrower.YawOf(farDir) - SP_TunnelGrower.YawOf(m_vMenuDir)));
		float rise = farPos[1] - m_vMenuPos[1];
		bool toTheRight = vector.Dot(farDir, right) > 0;
		entry.m_bSteer = true;
		entry.m_fAhead = along;
		entry.m_fTurn = turn;
		if (!toTheRight)
			entry.m_fTurn = -turn;

		string text;
		if (turn < 5)
			text = "straight";
		else if (turn > 170)
			text = "U-turn";
		else
		{
			string side = "left";
			if (toTheRight)
				side = "right";

			int turnDeg = Math.Round(turn);
			text = turnDeg.ToString() + " deg " + side;
		}

		int ahead = Math.Round(along);
		text = text + ", " + ahead.ToString() + " m ahead";
		if (rise > 0.3)
			text = text + ", " + rise.ToString(-1, 1) + " m up";
		else if (rise < -0.3)
		{
			float down = -rise;
			text = text + ", " + down.ToString(-1, 1) + " m down";
		}

		return text;
	}

	//------------------------------------------------------------------------------------------------
	//! Where to carry on after placing a piece: its own free opening that keeps the heading best, else the nearest other open end
	protected SP_HoverSocket NextEndAfter(int added, vector heading, vector fromPos)
	{
		SP_HoverSocket best;
		float bestScore = float.INFINITY;
		float headingYaw = SP_TunnelGrower.YawOf(heading);
		foreach (SP_HoverSocket socket : m_aFrontier)
		{
			float score;
			if (socket.m_iWorld == added)
				score = Math.AbsFloat(SP_TunnelConnect.Wrap(SP_TunnelGrower.YawOf(socket.m_vDir) - headingYaw));
			else
				score = 1000 + vector.Distance(socket.m_vPos, fromPos);

			if (score < bestScore)
			{
				best = socket;
				bestScore = score;
			}
		}

		return best;
	}

	//------------------------------------------------------------------------------------------------
	protected string GroupName(int group)
	{
		array<string> names = {"Normal tunnel", "Dripstone cave", "Rooms, junctions and doorways", "Entries", "Tunnel-to-cave breakthroughs", "Ends and caps", "Entrance adapters"};
		if (group < 0 || group >= names.Count())
			return "Other";

		return names[group];
	}

	//------------------------------------------------------------------------------------------------
	//! The generic kind a piece belongs to: from its theme (dug / cave / mix) and its kind
	protected int GroupOf(SP_TunnelPieceDef def)
	{
		// TT_Adapter_*: entrance pieces between the new dug tunnel ring and the old cave opening ring
		if (def.m_sName.Contains("Adapter"))
			return 6;

		int theme = SP_TunnelCatalog.ThemeOf(def.m_sName);
		if (theme == SP_TunnelTheme.MIX)
			return 4;

		if (theme == SP_TunnelTheme.CAVE)
			return 1;

		if (def.m_iKind == SP_TunnelKind.ENTRANCE)
			return 3;

		if (def.m_iKind == SP_TunnelKind.ROOM || def.m_iKind == SP_TunnelKind.DOORWAY)
			return 2;

		if (def.m_iKind == SP_TunnelKind.CAP || def.m_iKind == SP_TunnelKind.DOORCAP)
			return 5;

		return 0;
	}


	//------------------------------------------------------------------------------------------------
	protected override void OnMouseMoveEvent(float x, float y)
	{
		m_fMouseX = x;
		m_fMouseY = y;
		CheckTypeRow();
		if (m_DragSrc && !m_bDragging && Math.AbsFloat(x - m_fDragX) + Math.AbsFloat(y - m_fDragY) > DRAG_PIXELS)
		{
			m_bDragging = true;
			m_sHoverKey = "";
			Redraw();
			ShowHint();
		}

		if (!m_Hud && EnsureHud())
		{
			LoadCatalog();
			ShowHint();
		}

		int now = System.GetTickCount();
		if (now - m_iLastHover < HOVER_INTERVAL_MS)
			return;

		m_iLastHover = now;
		UpdateHover(x, y);
	}

	//------------------------------------------------------------------------------------------------
	protected string ShortName(string name)
	{
		if (name.IndexOf("TT_") == 0)
			return name.Substring(3, name.Length() - 3);

		return name;
	}

	//------------------------------------------------------------------------------------------------
	//! Build the assets that fit the open end: every piece of its kit with all the sides (openings) it can be joined by
	protected void BuildMenu()
	{
		m_aAssets.Clear();
		m_aFoot.Clear();
		m_iMenuHidden = 0;
		map<string, int> counts = new map<string, int>();
		foreach (SP_HoverPiece placed : m_aWorld)
		{
			string placedName = placed.m_Cat.m_aPieces[placed.m_iPiece].m_sName;
			int so_far;
			counts.Find(placedName, so_far);
			counts.Set(placedName, so_far + 1);
			IEntity entity = m_API.SourceToEntity(placed.m_Src);
			if (!entity)
				continue;

			vector mat[4];
			entity.GetWorldTransform(mat);
			m_aFoot.Insert(Footprint(placed.m_Cat.m_aPieces[placed.m_iPiece], mat[3], SP_TunnelGrower.YawOf(mat[2])));
		}

		foreach (int p, SP_TunnelPieceDef def : m_MenuCat.m_aPieces)
		{
			SP_Asset asset;
			foreach (int s, SP_TunnelSocketDef socket : def.m_aSockets)
			{
				if (!Fits(socket, m_MenuDef))
					continue;

				vector pos;
				float yaw;
				SP_TunnelGrower.Attach(m_vMenuPos, m_vMenuDir, socket, pos, yaw);
				bool duplicate = false;
				if (asset)
				{
					foreach (SP_MenuEntry known : asset.m_aSides)
					{
						if (SamePlacement(def, known.m_vPos, known.m_fYaw, pos, yaw))
						{
							duplicate = true;
							break;
						}
					}
				}

				if (duplicate)
					continue;

				SP_MenuEntry entry = new SP_MenuEntry();
				entry.m_Cat = m_MenuCat;
				entry.m_iPiece = p;
				entry.m_iSocket = s;
				entry.m_vPos = pos;
				entry.m_fYaw = yaw;
				int placedCount;
				counts.Find(def.m_sName, placedCount);
				entry.m_iPlaced = placedCount;
				string named = def.m_sName + "  x" + placedCount.ToString();
				entry.m_sLabel = named;
				if (def.m_aSockets.Count() > 2)
					entry.m_sLabel = string.Format("%1  (its opening %2, %3 more exits)", named, s + 1, def.m_aSockets.Count() - 1);
				else if (def.m_aSockets.Count() == 2)
				{
					entry.m_sLabel = named + "   " + Describe(entry, def.m_aSockets[1 - s], pos, yaw);
					if (def.m_sName.Contains("Adapter"))
					{
						if (s == 0)
							entry.m_sLabel = named + "   dug-tunnel end joins here, cave end stays free";
						else
							entry.m_sLabel = named + "   cave end joins here, dug-tunnel end stays free";
					}
				}

				// what the passage is after this piece (a two-opening piece: its other opening; otherwise the piece's size)
				entry.m_iGroup = GroupOf(def);
				int farSize = def.m_iSize;
				if (def.m_aSockets.Count() == 2)
					farSize = def.m_aSockets[1 - s].m_iSize;

				if (farSize == SP_TunnelSize.C)
					entry.m_iMove = 1;
				else if (farSize == SP_TunnelSize.P)
					entry.m_iMove = 2;

				SP_HoverFoot mine = Footprint(def, pos, yaw);
				foreach (SP_HoverFoot standing : m_aFoot)
				{
					if (mine.m_fY1 < standing.m_fY0 || mine.m_fY0 > standing.m_fY1)
						continue;

					if (QuadsOverlap(mine.m_aCorners, standing.m_aCorners))
					{
						entry.m_bOverlaps = true;
						break;
					}
				}

				if (entry.m_bOverlaps)
				{
					if (m_bHideOverlaps)
					{
						m_iMenuHidden++;
						continue;
					}

					entry.m_sLabel = entry.m_sLabel + "   [overlaps]";
				}

				if (!asset)
				{
					asset = new SP_Asset();
					asset.m_Cat = m_MenuCat;
					asset.m_iPiece = p;
					asset.m_sName = def.m_sName;
					asset.m_iGroup = entry.m_iGroup;
					asset.m_iMove = entry.m_iMove;
					asset.m_iPlaced = placedCount;
				}

				asset.m_aSides.Insert(entry);
			}

			if (asset)
			{
				// an adapter offers first the end that fits this opening: the cave end onto a cave opening, else the dug-tunnel end
				if (def.m_sName.Contains("Adapter") && asset.m_aSides.Count() == 2)
				{
					string targetName = m_MenuCat.m_aPieces[m_aWorld[m_iMenuWorld].m_iPiece].m_sName;
					if (SP_TunnelCatalog.ThemeOf(targetName) == SP_TunnelTheme.CAVE)
						asset.m_aSides.SwapItems(0, 1);
				}

				m_aAssets.Insert(asset);
			}
		}

		SortAssets();
	}

	//------------------------------------------------------------------------------------------------
	//! Order the assets by kind, then walk / crouch / prone, and give each a small glyph of what it does
	protected void SortAssets()
	{
		array<ref SP_Asset> sorted = {};
		for (int g = 0; g < GROUP_COUNT; g++)
		{
			for (int r = 0; r < 3; r++)
			{
				foreach (SP_Asset asset : m_aAssets)
				{
					if (asset.m_iGroup == g && asset.m_iMove == r)
						sorted.Insert(asset);
				}
			}
		}

		m_aAssets.Clear();
		foreach (SP_Asset copy : sorted)
		{
			bool left = false;
			bool right = false;
			bool uturn = false;
			int exits = 0;
			foreach (SP_MenuEntry side : copy.m_aSides)
			{
				if (!side.m_bSteer)
				{
					exits = copy.m_Cat.m_aPieces[copy.m_iPiece].m_aSockets.Count() - 1;
					continue;
				}

				if (Math.AbsFloat(side.m_fTurn) > 170)
					uturn = true;
				else if (side.m_fTurn >= 5)
					right = true;
				else if (side.m_fTurn <= -5)
					left = true;
			}

			if (exits > 0)
				copy.m_sGlyph = "*" + exits.ToString();
			else if (uturn)
				copy.m_sGlyph = "U";
			else if (left && right)
				copy.m_sGlyph = "<>";
			else if (right)
				copy.m_sGlyph = ">";
			else if (left)
				copy.m_sGlyph = "<";
			else
				copy.m_sGlyph = "^";

			m_aAssets.Insert(copy);
		}
	}

	//------------------------------------------------------------------------------------------------
	//! Start placing at one free opening: what fits there, the piece placed last (or the longest straight) selected, the preview
	protected void OpenMenu(SP_HoverSocket target)
	{
		ForgetPath();
		CloseMenu();
		SP_HoverPiece targetPiece = m_aWorld[target.m_iWorld];
		m_iMenuWorld = target.m_iWorld;
		m_iMenuSocket = target.m_iSocket;
		m_MenuCat = targetPiece.m_Cat;
		m_MenuDef = target.m_Def;
		m_vMenuPos = target.m_vPos;
		m_vMenuDir = target.m_vDir;
		m_vLastEnd = target.m_vPos;
		BuildMenu();
		m_iHover = -1;
		m_sHoverKey = "";
		if (m_aAssets.IsEmpty())
		{
			if (m_iMenuHidden > 0)
				SetHud(string.Format("Everything that fits %1, opening %2 would overlap (%3 pieces hidden): O shows them", targetPiece.m_sName, target.m_iSocket + 1, m_iMenuHidden));
			else
				SetHud(string.Format("Nothing in the catalog fits %1, opening %2 (size or kind)", targetPiece.m_sName, target.m_iSocket + 1));

			Redraw();
			DrawMenu();
			return;
		}

		m_bMenuOpen = true;
		InitialSelection();
		Redraw();
		ShowGhost();
		ShowHint();
	}

	//------------------------------------------------------------------------------------------------
	protected void CloseMenu()
	{
		m_bMenuOpen = false;
		m_bTypeOpen = false;
		m_aAssets.Clear();
		m_aRows.Clear();
		m_aFoot.Clear();
		DeleteGhost();
	}

	//------------------------------------------------------------------------------------------------
	//! The side of the selected piece that is highlighted (null when nothing is being placed)
	protected SP_MenuEntry SelectedEntry()
	{
		if (!m_bMenuOpen || m_iAsset < 0 || m_iAsset >= m_aAssets.Count())
			return null;

		SP_Asset asset = m_aAssets[m_iAsset];
		if (m_iSide < 0 || m_iSide >= asset.m_aSides.Count())
			return null;

		return asset.m_aSides[m_iSide];
	}

	//------------------------------------------------------------------------------------------------
	//! Which side of a piece comes nearest to a turn and a walk / crouch / prone kind
	protected int PickSide(SP_Asset asset, float turn, int move)
	{
		int best = 0;
		float bestScore = 100000;
		foreach (int s, SP_MenuEntry entry : asset.m_aSides)
		{
			float score = 0;
			if (entry.m_iMove != move)
				score += 1000;

			if (entry.m_bSteer)
				score += Math.AbsFloat(entry.m_fTurn - turn);

			if (score < bestScore)
			{
				bestScore = score;
				best = s;
			}
		}

		return best;
	}

	//------------------------------------------------------------------------------------------------
	//! The piece placed last again (the side nearest its turn), else the longest straight walking piece
	protected void InitialSelection()
	{
		m_iAsset = 0;
		m_iSide = 0;
		int found = -1;
		if (!m_sLastAsset.IsEmpty())
		{
			foreach (int i, SP_Asset known : m_aAssets)
			{
				if (known.m_sName == m_sLastAsset)
					found = i;
			}
		}

		if (found >= 0)
		{
			m_iAsset = found;
			m_iSide = PickSide(m_aAssets[found], m_fLastTurn, m_iLastMove);
			return;
		}

		float bestAhead = -1;
		foreach (int a, SP_Asset candidate : m_aAssets)
		{
			foreach (int s, SP_MenuEntry entry : candidate.m_aSides)
			{
				if (!entry.m_bSteer || entry.m_iMove != 0 || Math.AbsFloat(entry.m_fTurn) > 1)
					continue;

				if (entry.m_fAhead > bestAhead)
				{
					bestAhead = entry.m_fAhead;
					m_iAsset = a;
					m_iSide = s;
				}
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	protected void SelectVariant(int asset, int side)
	{
		m_iAsset = asset;
		m_iSide = side;
		ShowGhost();
		ShowHint();
	}

	//------------------------------------------------------------------------------------------------
	//! Tab / Q: the next / previous side of the same piece (another of its openings joins the open end)
	protected void CycleSide(int dir)
	{
		SP_MenuEntry current = SelectedEntry();
		if (!current)
			return;

		int count = m_aAssets[m_iAsset].m_aSides.Count();
		if (count < 2)
		{
			SetHud("This piece has only one side that fits here");
			return;
		}

		SelectVariant(m_iAsset, (m_iSide + dir + count) % count);
	}

	//------------------------------------------------------------------------------------------------
	//! W / C / P: the walking / crouching / proning piece nearest the current one (same turn, same kind if possible)
	protected void StanceJump(int move)
	{
		SP_MenuEntry current = SelectedEntry();
		int bestAsset = -1;
		int bestSide = -1;
		float bestScore = 100000;
		foreach (int a, SP_Asset asset : m_aAssets)
		{
			foreach (int s, SP_MenuEntry entry : asset.m_aSides)
			{
				if (entry.m_iMove != move)
					continue;

				float score = 0;
				if (current)
				{
					if (entry.m_bSteer && current.m_bSteer)
						score += Math.AbsFloat(entry.m_fTurn - current.m_fTurn);

					if (entry.m_iGroup != current.m_iGroup)
						score += 500;
				}

				if (score < bestScore)
				{
					bestScore = score;
					bestAsset = a;
					bestSide = s;
				}
			}
		}

		if (bestAsset < 0)
		{
			array<string> names = {"walking", "crouching", "prone"};
			SetHud("No " + names[move] + " piece fits this open end");
			return;
		}

		SelectVariant(bestAsset, bestSide);
	}

	//------------------------------------------------------------------------------------------------
	protected void ShowHint()
	{
		DrawMenu();
		if (m_bDragging)
		{
			SetHud("Path: let go over the opening it should lead to (anywhere else cancels)");
			return;
		}

		if (m_bMenuOpen)
		{
			SP_MenuEntry chosen = SelectedEntry();
			if (chosen)
			{
				string warning = "";
				if (chosen.m_bOverlaps)
					warning = "WARNING, overlaps a placed piece (maybe a false alarm): ";

				SP_Asset asset = m_aAssets[m_iAsset];
				SetHud(warning + GroupName(asset.m_iGroup) + ": " + chosen.m_sLabel + string.Format("   [side %1/%2]", m_iSide + 1, asset.m_aSides.Count()) + m_sNote);
			}

			return;
		}

		SP_HoverSocket picked = PickedSocket();
		if (!picked)
		{
			if (m_iHover >= 0)
			{
				SP_HoverSocket over = m_aAll[m_iHover];
				if (m_bMenuMode)
					SetHud(string.Format("Entrance snap: click to place a piece at %1, opening %2", m_aWorld[over.m_iWorld].m_sName, over.m_iSocket + 1));
				else
					SetHud(string.Format("Entrance snap: click to MOVE %1, opening %2", m_aWorld[over.m_iWorld].m_sName, over.m_iSocket + 1));
			}
			else
			{
				if (m_bMenuMode)
					SetHud("Entrance snap: N picks an open end, or click one" + m_sNote);
				else
					SetHud("Entrance snap: point at a free opening of the piece that should MOVE and click (M: placing instead)" + m_sNote);
			}

			return;
		}

		string head = string.Format("Moving %1 (opening %2)", m_aWorld[picked.m_iWorld].m_sName, picked.m_iSocket + 1);
		if (m_iHover < 0)
		{
			SetHud(head + ": point at the free opening it should join and click (Esc: cancel)");
			return;
		}

		SP_HoverSocket target = m_aAll[m_iHover];
		string where = string.Format("%1, opening %2", m_aWorld[target.m_iWorld].m_sName, target.m_iSocket + 1);
		if (m_sWhy != "")
			SetHud(head + " -> " + where + ": does NOT fit, " + m_sWhy);
		else
			SetHud(head + " -> " + where + ": click to join");
	}

	//------------------------------------------------------------------------------------------------
	//! Keys N / B: the next / previous open end, nearest first from where the walk began; the placement starts there.
	//! Clicking an opening by hand ends the walk.
	protected void JumpEnd(int dir)
	{
		if (m_aFrontier.IsEmpty())
		{
			SetHud("No open end in the world");
			return;
		}

		if (!m_bCycling)
		{
			m_bCycling = true;
			m_iEndCycle = -1;
			m_vCycleAnchor = m_vLastEnd;
			if (m_bMenuOpen)
				m_vCycleAnchor = m_vMenuPos;
			else if (m_vLastEnd == vector.Zero)
			{
				BaseWorld world = m_API.GetWorld();
				vector mat[4];
				world.GetCamera(world.GetCurrentCameraId(), mat);
				m_vCycleAnchor = mat[3];
			}
		}

		array<SP_HoverSocket> ends = {};
		array<float> distances = {};
		foreach (SP_HoverSocket socket : m_aFrontier)
		{
			float distance = vector.Distance(socket.m_vPos, m_vCycleAnchor);
			if (distance < 1 && m_bMenuOpen)
				continue;

			int at = ends.Count();
			while (at > 0 && distances[at - 1] > distance)
			{
				at--;
			}

			ends.InsertAt(socket, at);
			distances.InsertAt(distance, at);
		}

		if (ends.IsEmpty())
		{
			SetHud("No other open end");
			return;
		}

		int count = ends.Count();
		if (m_iEndCycle < 0 && dir < 0)
			m_iEndCycle = count - 1;
		else
			m_iEndCycle = (m_iEndCycle + dir + count) % count;

		SP_HoverSocket target = ends[m_iEndCycle];
		if (m_bMenuMode)
		{
			OpenMenu(target);
			return;
		}

		CloseMenu();
		m_vLastEnd = target.m_vPos;
		m_sHoverKey = "";
		Redraw();
		SetHud(string.Format("Open end %1 of %2: %3, opening %4", m_iEndCycle + 1, count, m_aWorld[target.m_iWorld].m_sName, target.m_iSocket + 1));
		ShowHint();
	}

	//------------------------------------------------------------------------------------------------
	protected override void OnKeyPressEvent(KeyCode key, bool isAutoRepeat)
	{
		// The first keys that reach the tool are logged, to see which ones the editor keeps for itself (ctrl+x is its Cut)
		if (m_iKeysLogged < 60 && !isAutoRepeat)
		{
			m_iKeysLogged++;
			int code = key;
			Print(string.Format("SP_TunnelSnapTool: key %1 (ctrl %2, alt %3, shift %4)", code, GetModifierKeyState(ModifierKey.CONTROL), GetModifierKeyState(ModifierKey.ALT), GetModifierKeyState(ModifierKey.SHIFT)));
		}

		// another random path between the same two openings
		if (!m_bMenuOpen && !m_aPathMade.IsEmpty() && (key == KeyCode.KC_SPACE || key == KeyCode.KC_RETURN))
		{
			RunPath(true);
			return;
		}

		if (m_PathStart && key == KeyCode.KC_ESCAPE)
		{
			ForgetPath();
			Redraw();
			ShowHint();
			return;
		}

		// any other key of the tool ends "another one": X then removes the selected path, which stays selected until then
		if (key == KeyCode.KC_M || key == KeyCode.KC_N || key == KeyCode.KC_B || key == KeyCode.KC_X || key == KeyCode.KC_BACK || key == KeyCode.KC_DELETE || key == KeyCode.KC_ESCAPE)
			ForgetPath();

		if (key == KeyCode.KC_M)
		{
			m_bMenuMode = !m_bMenuMode;
			CloseMenu();
			ClearPick();
			m_sHoverKey = "";
			Redraw();
			if (m_bMenuMode)
				SetHud("Placing: N picks an open end, or click one");
			else
				SetHud("Moving a placed piece: click one of its openings, then the opening it should join (M: back to placing)");

			ShowHint();
			return;
		}

		if (key == KeyCode.KC_N)
		{
			JumpEnd(1);
			return;
		}

		if (key == KeyCode.KC_B)
		{
			JumpEnd(-1);
			return;
		}

		// remove: X (also with ctrl), Backspace or Delete, whichever of them the editor lets through
		if (key == KeyCode.KC_X || key == KeyCode.KC_BACK || key == KeyCode.KC_DELETE)
		{
			RemoveSelected();
			return;
		}

		if (key == KeyCode.KC_O)
		{
			m_bHideOverlaps = !m_bHideOverlaps;
			if (m_bMenuOpen)
			{
				string keep = m_sLastAsset;
				SP_MenuEntry current = SelectedEntry();
				if (current)
					m_sLastAsset = m_aAssets[m_iAsset].m_sName;

				BuildMenu();
				if (m_aAssets.IsEmpty())
				{
					m_sLastAsset = keep;
					CloseMenu();
					Redraw();
					SetHud("Nothing fits here without overlapping (O: show the overlapping ones)");
					ShowHint();
					return;
				}

				InitialSelection();
				m_sLastAsset = keep;
				ShowGhost();
			}

			ShowHint();
			return;
		}

		if (m_bMenuOpen)
		{
			if (key != KeyCode.KC_UP && key != KeyCode.KC_DOWN)
				m_bTypeOpen = false;

			if (key == KeyCode.KC_LEFT)
				Steer(-1);
			else if (key == KeyCode.KC_RIGHT)
				Steer(1);
			else if (key == KeyCode.KC_UP)
				KindStep(-1);
			else if (key == KeyCode.KC_DOWN)
				KindStep(1);
			else if (key == KeyCode.KC_PRIOR)
				PieceStep(-1);
			else if (key == KeyCode.KC_NEXT)
				PieceStep(1);
			else if (key == KeyCode.KC_TAB)
				CycleSide(1);
			else if (key == KeyCode.KC_1)
				StanceJump(0);
			else if (key == KeyCode.KC_2)
				StanceJump(1);
			else if (key == KeyCode.KC_3)
				StanceJump(2);
			else if (key == KeyCode.KC_SPACE || key == KeyCode.KC_RETURN)
				PlaceSelected();
			else if (key == KeyCode.KC_ESCAPE)
			{
				CloseMenu();
				Redraw();
				ShowHint();
			}

			return;
		}

		if (key != KeyCode.KC_ESCAPE)
			return;

		if (m_PickSrc)
		{
			ClearPick();
			Redraw();
			ShowHint();
			return;
		}

		m_API.ClearEntitySelection();
	}

	//------------------------------------------------------------------------------------------------
	//! Our TT kit is the only one this tool places (the EoH pack is not supported here)
	protected bool LoadCatalog()
	{
		if (!m_aCatalogs.IsEmpty())
			return true;

		m_aUnknown.Clear();
		m_Cache.Clear();
		SP_TunnelCatalog catalog = new SP_TunnelCatalog(SP_TunnelCatalog.KIT_TT);
		if (catalog.Get(m_API, false) && !catalog.m_aPieces.IsEmpty())
		{
			m_aCatalogs.Insert(catalog);
			return true;
		}

		SetHud("Entrance snap: no piece catalog yet. Use Rebuild TT catalog in the tool settings.");
		return false;
	}

	//------------------------------------------------------------------------------------------------
	protected string GroupShort(int group)
	{
		array<string> names = {"Normal tunnel", "Dripstone cave", "Rooms", "Entries", "Cave breakthroughs", "Ends and caps", "Adapters"};
		if (group < 0 || group >= names.Count())
			return "Other";

		return names[group];
	}

	//------------------------------------------------------------------------------------------------
	//! How many pieces of a type fit the open end
	protected int KindPieces(int group)
	{
		int count = 0;
		foreach (SP_Asset asset : m_aAssets)
		{
			if (asset.m_iGroup == group)
				count++;
		}

		return count;
	}

	//------------------------------------------------------------------------------------------------
	//! How many pieces of the current type have a side that ends walking (0), crouching (1) or prone (2)
	protected int StanceCount(int move)
	{
		if (!SelectedEntry())
			return 0;

		int group = m_aAssets[m_iAsset].m_iGroup;
		int count = 0;
		foreach (SP_Asset asset : m_aAssets)
		{
			if (asset.m_iGroup != group)
				continue;

			foreach (SP_MenuEntry side : asset.m_aSides)
			{
				if (side.m_iMove == move)
				{
					count++;
					break;
				}
			}
		}

		return count;
	}

	//------------------------------------------------------------------------------------------------
	//! The piece and side of the current type that lean further to one side than the current one (the gentlest turn first),
	//! keeping walk / crouch / prone and, as far as the choice allows, the length
	protected bool FindSteer(int dir, out int bestAsset, out int bestSide)
	{
		bestAsset = -1;
		bestSide = -1;
		SP_MenuEntry current = SelectedEntry();
		if (!current)
			return false;

		int group = m_aAssets[m_iAsset].m_iGroup;
		float currentTurn = 0;
		float currentAhead = 0;
		if (current.m_bSteer)
		{
			currentTurn = current.m_fTurn;
			currentAhead = current.m_fAhead;
		}

		float smallest = 100000;
		foreach (SP_Asset first : m_aAssets)
		{
			if (first.m_iGroup != group)
				continue;

			foreach (SP_MenuEntry entry : first.m_aSides)
			{
				if (!entry.m_bSteer || entry.m_iMove != current.m_iMove)
					continue;

				float step = (entry.m_fTurn - currentTurn) * dir;
				if (step >= 1 && step < smallest)
					smallest = step;
			}
		}

		if (smallest > 99999)
			return false;

		float bestLength = 100000;
		foreach (int a, SP_Asset second : m_aAssets)
		{
			if (second.m_iGroup != group)
				continue;

			foreach (int s, SP_MenuEntry candidate : second.m_aSides)
			{
				if (!candidate.m_bSteer || candidate.m_iMove != current.m_iMove)
					continue;

				float lean = (candidate.m_fTurn - currentTurn) * dir;
				if (lean < 1 || lean > smallest + 1)
					continue;

				float length = Math.AbsFloat(candidate.m_fAhead - currentAhead);
				if (length < bestLength)
				{
					bestLength = length;
					bestAsset = a;
					bestSide = s;
				}
			}
		}

		return bestAsset >= 0;
	}

	//------------------------------------------------------------------------------------------------
	//! The piece of a type nearest the current choice (same walk / crouch / prone, nearest turn)
	protected void SelectBestInKind(int group)
	{
		SP_MenuEntry current = SelectedEntry();
		float turn = 0;
		int move = 0;
		if (current)
		{
			move = current.m_iMove;
			if (current.m_bSteer)
				turn = current.m_fTurn;
		}

		int bestAsset = -1;
		int bestSide = 0;
		float best = 100000;
		foreach (int a, SP_Asset asset : m_aAssets)
		{
			if (asset.m_iGroup != group)
				continue;

			int side = PickSide(asset, turn, move);
			SP_MenuEntry entry = asset.m_aSides[side];
			float score = 0;
			if (entry.m_iMove != move)
				score += 1000;

			if (entry.m_bSteer)
				score += Math.AbsFloat(entry.m_fTurn - turn);

			if (score < best)
			{
				best = score;
				bestAsset = a;
				bestSide = side;
			}
		}

		if (bestAsset >= 0)
			SelectVariant(bestAsset, bestSide);
	}

	//------------------------------------------------------------------------------------------------
	//! PageUp / PageDown: the previous / next piece of the current type (the side nearest the current turn)
	protected void PieceStep(int dir)
	{
		SP_MenuEntry current = SelectedEntry();
		if (!current)
			return;

		int group = m_aAssets[m_iAsset].m_iGroup;
		array<int> members = {};
		int at = 0;
		foreach (int i, SP_Asset asset : m_aAssets)
		{
			if (asset.m_iGroup != group)
				continue;

			if (i == m_iAsset)
				at = members.Count();

			members.Insert(i);
		}

		if (members.Count() < 2)
		{
			SetHud("Only one piece of this type fits this open end");
			return;
		}

		float turn = 0;
		if (current.m_bSteer)
			turn = current.m_fTurn;

		int next = members[(at + dir + members.Count()) % members.Count()];
		SelectVariant(next, PickSide(m_aAssets[next], turn, current.m_iMove));
	}

	//------------------------------------------------------------------------------------------------
	//! X: delete the selected pieces of the kit (one undo step); the open end that comes free again where a removed piece was
	//! joined is selected, so a wrong piece is replaced with one more key
	protected void RemoveSelected()
	{
		if (m_aCatalogs.IsEmpty())
			return;

		array<IEntitySource> doomed = {};
		int selected = m_API.GetSelectedEntitiesCount();
		for (int i = 0; i < selected; i++)
		{
			IEntitySource src = m_API.GetSelectedEntity(i);
			if (!src || src.GetParent())
				continue;

			if (PieceOfSource(src) >= 0)
				doomed.Insert(src);
		}

		if (doomed.IsEmpty())
		{
			SetHud("Remove (X, Ctrl+X, Backspace) takes the selected pieces of the kit: none is selected");
			return;
		}

		// where they are joined to others: their openings, taken before they are gone
		RefreshWorld();
		array<vector> joints = {};
		foreach (SP_HoverSocket socket : m_aAll)
		{
			foreach (IEntitySource gone : doomed)
			{
				if (m_aWorld[socket.m_iWorld].m_Src == gone)
				{
					joints.Insert(socket.m_vPos);
					break;
				}
			}
		}

		CloseMenu();
		ClearPick();
		m_API.BeginEntityAction("Entrance snap: remove piece");
		foreach (IEntitySource doomedSrc : doomed)
		{
			m_API.DeleteEntity(doomedSrc);
		}

		m_API.EndEntityAction();
		m_API.ClearEntitySelection();
		int removed = doomed.Count();
		Print(string.Format("SP_TunnelSnapTool: removed %1 piece(s)", removed));

		RefreshWorld();
		m_iHover = -1;
		m_sHoverKey = "";
		m_bCycling = false;
		SP_HoverSocket reopened;
		float nearest = 1.0;
		foreach (SP_HoverSocket open : m_aFrontier)
		{
			foreach (vector joint : joints)
			{
				float distance = vector.Distance(open.m_vPos, joint);
				if (distance < nearest)
				{
					nearest = distance;
					reopened = open;
				}
			}
		}

		if (reopened)
		{
			if (m_bMenuMode)
			{
				OpenMenu(reopened);
				return;
			}
		}

		Redraw();
		ShowHint();
		SetHud(string.Format("Removed %1 piece(s)", removed));
	}

	//------------------------------------------------------------------------------------------------
	//! The types fold away again 1.5 s after the last Up / Down (checked from the mouse events, never per frame)
	protected void CheckTypeRow()
	{
		if (!m_bTypeOpen)
			return;

		if (System.GetTickCount() - m_iTypeOpenTick < 1500)
			return;

		m_bTypeOpen = false;
		ShowHint();
	}

	//------------------------------------------------------------------------------------------------
	//! Up / Down: the previous / next TYPE of piece that has anything fitting this open end. The other types are shown on the
	//! strip while this goes on.
	protected void KindStep(int dir)
	{
		if (!SelectedEntry())
			return;

		int group = m_aAssets[m_iAsset].m_iGroup;
		for (int k = 1; k <= GROUP_COUNT; k++)
		{
			int other = (group + dir * k + GROUP_COUNT * 2) % GROUP_COUNT;
			if (other != group && KindPieces(other) > 0)
			{
				m_bTypeOpen = true;
				m_iTypeOpenTick = System.GetTickCount();
				SelectBestInKind(other);
				return;
			}
		}

		SetHud("Only one type of piece fits this open end");
	}

	//------------------------------------------------------------------------------------------------
	//! Left / Right. In the normal tunnel type this steers: the next piece and side that lean further that way (the gentlest turn
	//! first; again = sharper). In every other type there is no turn to steer: it moves along the pieces of the type.
	protected void Steer(int dir)
	{
		SP_MenuEntry current = SelectedEntry();
		if (!current)
			return;

		if (m_aAssets[m_iAsset].m_iGroup != 0 || !current.m_bSteer)
		{
			PieceStep(dir);
			return;
		}

		int a;
		int s;
		if (!FindSteer(dir, a, s))
		{
			if (dir < 0)
				SetHud("No sharper left turn fits here");
			else
				SetHud("No sharper right turn fits here");

			return;
		}

		SelectVariant(a, s);
	}

	//------------------------------------------------------------------------------------------------
	protected string TurnLabel(float turn)
	{
		if (Math.AbsFloat(turn) > 170)
			return "U";

		if (Math.AbsFloat(turn) < 5)
			return "^";

		int degrees = Math.Round(Math.AbsFloat(turn));
		if (turn > 0)
			return degrees.ToString() + "R";

		return degrees.ToString() + "L";
	}

	//------------------------------------------------------------------------------------------------
	//! The turn levels of the normal tunnel type, left to right: one variant for each distinct turn (the one nearest the current
	//! length, the current one for its own level), same walk / crouch / prone as the current choice. Returns where the current one is.
	protected int SteerLadder(array<int> assets, array<int> sides)
	{
		SP_MenuEntry current = SelectedEntry();
		if (!current || !current.m_bSteer)
			return -1;

		int group = m_aAssets[m_iAsset].m_iGroup;
		array<float> turns = {};
		array<float> distances = {};
		foreach (int a, SP_Asset asset : m_aAssets)
		{
			if (asset.m_iGroup != group)
				continue;

			foreach (int s, SP_MenuEntry entry : asset.m_aSides)
			{
				if (!entry.m_bSteer || entry.m_iMove != current.m_iMove)
					continue;

				float distance = Math.AbsFloat(entry.m_fAhead - current.m_fAhead);
				bool isCurrent = a == m_iAsset && s == m_iSide;
				if (isCurrent)
					distance = -1;

				int level = -1;
				for (int i = 0; i < turns.Count(); i++)
				{
					if (Math.AbsFloat(turns[i] - entry.m_fTurn) < 1)
					{
						level = i;
						break;
					}
				}

				if (level >= 0)
				{
					if (distance < distances[level])
					{
						assets.Set(level, a);
						sides.Set(level, s);
						distances.Set(level, distance);
					}

					continue;
				}

				int at = turns.Count();
				while (at > 0 && turns[at - 1] > entry.m_fTurn)
				{
					at--;
				}

				turns.InsertAt(entry.m_fTurn, at);
				distances.InsertAt(distance, at);
				assets.InsertAt(a, at);
				sides.InsertAt(s, at);
			}
		}

		for (int j = 0; j < assets.Count(); j++)
		{
			if (assets[j] == m_iAsset && sides[j] == m_iSide)
				return j;
		}

		return -1;
	}


	//------------------------------------------------------------------------------------------------
	//! Text with a background, drawn twice a hair apart so it looks bold (the second copy has no background). Returns its width.
	protected float AddBold(BaseWorld world, float x, float y, string text, int colour, int background)
	{
		m_aRows.Insert(DebugTextScreenSpace.Create(world, text, DebugTextFlags.FACE_CAMERA, x, y, STRIP_TEXT, colour, background));
		m_aRows.Insert(DebugTextScreenSpace.Create(world, text, DebugTextFlags.FACE_CAMERA, x + BOLD_OFFSET, y, STRIP_TEXT, colour, 0x00000000));
		return text.Length() * STRIP_CHAR_W + 4;
	}

	//------------------------------------------------------------------------------------------------
	protected void NewRow()
	{
		m_fChipX = STRIP_X;
		m_fChipY += STRIP_ROW_H;
	}

	//------------------------------------------------------------------------------------------------
	//! The name of a row (TYPE, PIECE, ...) in amber
	protected void AddRowLabel(BaseWorld world, string text)
	{
		string padded = " " + text + " ";
		m_fChipX += AddBold(world, m_fChipX, m_fChipY, padded, 0xFFFFC857, 0xE61B1F27) + 3;
	}

	//------------------------------------------------------------------------------------------------
	//! A choice on the strip. state: 0 plain, 1 not available here (dim), 2 the current choice (blue)
	protected void AddPill(BaseWorld world, string text, int state)
	{
		string padded = " " + text + " ";
		float width = padded.Length() * STRIP_CHAR_W + 4;
		if (m_fChipX + width > m_fChipLimit && m_fChipX > STRIP_X)
			NewRow();

		int colour = 0xFFD7DEE8;
		int background = 0xE62A303B;
		if (state == 1)
		{
			colour = 0xFF6B7380;
			background = 0xAA1B1F27;
		}
		else if (state == 2)
		{
			colour = 0xFFFFFFFF;
			background = 0xFF2F6FDE;
		}

		m_fChipX += AddBold(world, m_fChipX, m_fChipY, padded, colour, background) + 3;
	}

	//------------------------------------------------------------------------------------------------
	//! A key and what it does, like a keycap with a label. state: 0 works now, 1 can't here (dim), 2 the current choice (blue)
	protected void AddKeyCap(BaseWorld world, string key, string label, int state)
	{
		string keyText = " " + key + " ";
		string labelText = "";
		if (!label.IsEmpty())
			labelText = " " + label + " ";

		float widthKey = keyText.Length() * STRIP_CHAR_W + 4;
		float widthLabel = labelText.Length() * STRIP_CHAR_W + 4;
		if (m_fChipX + widthKey + widthLabel > m_fChipLimit && m_fChipX > STRIP_X)
			NewRow();

		int keyColour = 0xFFFFFFFF;
		int keyBackground = 0xFF3A4252;
		int labelColour = 0xFFD7DEE8;
		int labelBackground = 0xE61B1F27;
		if (state == 1)
		{
			keyColour = 0xFF6B7380;
			keyBackground = 0xAA262A33;
			labelColour = 0xFF6B7380;
			labelBackground = 0xAA1B1F27;
		}
		else if (state == 2)
		{
			keyBackground = 0xFF2F6FDE;
			labelColour = 0xFFFFFFFF;
			labelBackground = 0xFF1F4FA3;
		}

		m_fChipX += AddBold(world, m_fChipX, m_fChipY, keyText, keyColour, keyBackground);
		if (!labelText.IsEmpty())
			m_fChipX += AddBold(world, m_fChipX, m_fChipY, labelText, labelColour, labelBackground);

		m_fChipX += 4;
	}

	//------------------------------------------------------------------------------------------------
	protected int AvailState(bool available)
	{
		if (available)
			return 0;

		return 1;
	}

	//------------------------------------------------------------------------------------------------
	//! The strip at the top left, one row per decision, redrawn whenever the state changes (never per frame):
	//!   TYPE     only the chosen type; the other types appear while you navigate with Up / Down
	//!   STEER    (normal tunnel) the turn levels, left to right, Left / Right moves along them
	//!   PIECE    (every other type) the pieces of the type, Left / Right moves along them
	//!   OPTIONS  stance (1 2 3), side (Tab), piece within the type (PgUp / PgDn)       KEYS  the rest
	//! Keycaps are bright when the key does something now, dim when it can't here, blue for the current choice.
	protected void DrawMenu()
	{
		m_aRows.Clear();
		BaseWorld world = m_API.GetWorld();
		if (!world)
			return;

		m_fChipLimit = m_API.GetScreenWidth() - STRIP_X * 2;
		if (m_fChipLimit < 500)
			m_fChipLimit = 500;

		m_fChipX = STRIP_X;
		m_fChipY = STRIP_Y;
		int ends = m_aFrontier.Count();
		if (!m_bMenuOpen)
		{
			AddRowLabel(world, "KEYS");
			if (m_bMenuMode)
			{
				AddKeyCap(world, "N", string.Format("first open end (%1 free)", ends), AvailState(ends > 0));
				AddKeyCap(world, "Click", "an open end", AvailState(ends > 0));
				AddKeyCap(world, "Drag / Shift+Click", "opening to opening: path", AvailState(ends > 1));
				if (!m_aPathMade.IsEmpty())
					AddKeyCap(world, "Space", "another path", 2);
				AddKeyCap(world, "X / Ctrl+X / Bksp", "remove selected piece", 0);
				AddKeyCap(world, "M", "move a placed piece", 0);
			}
			else
			{
				AddKeyCap(world, "Click", "the opening of the piece to move, then the opening it joins", 0);
				AddKeyCap(world, "M", "back to placing", 0);
			}

			AddKeyCap(world, "Esc", "clear", 0);
			return;
		}

		SP_Asset chosen = m_aAssets[m_iAsset];
		SP_MenuEntry current = SelectedEntry();
		int move = 0;
		if (current)
			move = current.m_iMove;

		bool normal = chosen.m_iGroup == 0 && current != null && current.m_bSteer;

		// the pieces of the chosen type, and where the chosen one is among them
		array<int> members = {};
		int at = 0;
		foreach (int i, SP_Asset asset : m_aAssets)
		{
			if (asset.m_iGroup != chosen.m_iGroup)
				continue;

			if (i == m_iAsset)
				at = members.Count();

			members.Insert(i);
		}

		// TYPE: just the chosen one; its siblings only while navigating with Up / Down
		AddRowLabel(world, "TYPE");
		if (m_bTypeOpen)
		{
			for (int g = 0; g < GROUP_COUNT; g++)
			{
				int pieces = KindPieces(g);
				string name = GroupShort(g) + string.Format(" %1", pieces);
				if (pieces == 0)
					AddPill(world, name, 1);
				else if (g == chosen.m_iGroup)
					AddPill(world, name, 2);
				else
					AddPill(world, name, 0);
			}
		}
		else
		{
			int types = 0;
			for (int t = 0; t < GROUP_COUNT; t++)
			{
				if (KindPieces(t) > 0)
					types++;
			}

			AddPill(world, GroupShort(chosen.m_iGroup) + string.Format(" %1", members.Count()), 2);
			AddKeyCap(world, "Up/Down", "other types", AvailState(types > 1));
		}

		NewRow();
		if (normal)
		{
			// STEER: the turn levels, left to right
			array<int> ladderAssets = {};
			array<int> ladderSides = {};
			int here = SteerLadder(ladderAssets, ladderSides);
			AddRowLabel(world, "STEER");
			AddKeyCap(world, "Left/Right", "", 0);
			int from = here - 2;
			if (from < 0)
				from = 0;

			int to = from + 4;
			if (to > ladderAssets.Count() - 1)
				to = ladderAssets.Count() - 1;

			from = to - 4;
			if (from < 0)
				from = 0;

			if (from > 0)
				AddPill(world, "...", 1);

			for (int l = from; l <= to; l++)
			{
				SP_Asset step = m_aAssets[ladderAssets[l]];
				SP_MenuEntry stepSide = step.m_aSides[ladderSides[l]];
				int stepState = 0;
				if (l == here)
					stepState = 2;

				AddPill(world, ShortName(step.m_sName) + " " + TurnLabel(stepSide.m_fTurn), stepState);
			}

			if (to < ladderAssets.Count() - 1)
				AddPill(world, "...", 1);
		}
		else
		{
			// PIECE: the pieces of this type, a window of five round the chosen one
			AddRowLabel(world, "PIECE");
			AddKeyCap(world, "Left/Right", "", 0);
			int pFrom = at - 2;
			if (pFrom < 0)
				pFrom = 0;

			int pTo = pFrom + 4;
			if (pTo > members.Count() - 1)
				pTo = members.Count() - 1;

			pFrom = pTo - 4;
			if (pFrom < 0)
				pFrom = 0;

			if (pFrom > 0)
				AddPill(world, "...", 1);

			for (int m = pFrom; m <= pTo; m++)
			{
				SP_Asset item = m_aAssets[members[m]];
				int itemState = 0;
				if (members[m] == m_iAsset)
					itemState = 2;

				AddPill(world, ShortName(item.m_sName) + " " + item.m_sGlyph + string.Format(" x%1", item.m_iPlaced), itemState);
			}

			if (pTo < members.Count() - 1)
				AddPill(world, "...", 1);
		}

		// OPTIONS: stance, side, piece within the type
		NewRow();
		AddRowLabel(world, "OPTIONS");
		int walkers = StanceCount(0);
		int crouchers = StanceCount(1);
		int pronePieces = StanceCount(2);
		int stanceWalk = AvailState(walkers > 0);
		if (walkers > 0 && move == 0)
			stanceWalk = 2;

		int stanceCrouch = AvailState(crouchers > 0);
		if (crouchers > 0 && move == 1)
			stanceCrouch = 2;

		int stanceProne = AvailState(pronePieces > 0);
		if (pronePieces > 0 && move == 2)
			stanceProne = 2;

		AddKeyCap(world, "1", string.Format("walk %1", walkers), stanceWalk);
		AddKeyCap(world, "2", string.Format("crouch %1", crouchers), stanceCrouch);
		AddKeyCap(world, "3", string.Format("prone %1", pronePieces), stanceProne);
		int sides = chosen.m_aSides.Count();
		AddKeyCap(world, "Tab", string.Format("side %1/%2", m_iSide + 1, sides), AvailState(sides > 1));
		AddKeyCap(world, "PgUp/PgDn", string.Format("piece %1/%2", at + 1, members.Count()), AvailState(members.Count() > 1));

		// KEYS: the rest
		NewRow();
		AddRowLabel(world, "KEYS");
		AddKeyCap(world, "Space", "place", AvailState(current != null));
		AddKeyCap(world, "X / Ctrl+X / Bksp", "remove selected", 0);
		AddKeyCap(world, "N/B", string.Format("other open end %1", ends), AvailState(ends > 1));
		string overlaps = "shown";
		if (m_bHideOverlaps)
			overlaps = "hidden";

		AddKeyCap(world, "O", "overlaps " + overlaps, 0);
		AddKeyCap(world, "Drag / Shift+Click", "path to another opening", AvailState(ends > 1));
		AddKeyCap(world, "Esc", "close", 0);
	}
}
#endif
