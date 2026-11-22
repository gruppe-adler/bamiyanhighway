#ifdef WORKBENCH
//! The EoH Modular Tunnel Pack as the generator sees it: every usable piece, its bounds, and its sockets (where other
//! pieces attach). Built once from the pack's own memory points (bones on each model), with the facing of each socket
//! found by tracing, then saved to $profile:SP_TunnelCatalog.txt and loaded from there, so layouts stay repeatable.

class SP_TunnelKind
{
	static const int STRAIGHT = 0;
	static const int TURN = 1;		// Left90 / Right90
	static const int BEND = 2;		// L_Bend / R_Bend: a sideways wiggle that ends on the same line
	static const int HUMP = 3;		// Up_Bend: hump in the roof, same height at both ends
	static const int WATER = 4;		// Water_Trap
	static const int SLOPE = 5;		// Down_Slope (entered from the far end it goes up)
	static const int UPTURN = 6;	// Up_Turn_L / R: climb and turn in one
	static const int UTURN = 7;
	static const int LADDER = 8;	// S_Ladder_Parallel: two levels, four sockets
	static const int CAP = 9;		// S_Blocked_Path
	static const int DOORWAY = 10;	// S/C/P_Doorway: corridor <-> room doorframe
	static const int DOORCAP = 11;	// Blocked_Doorway: closes a room doorframe
	static const int ROOM = 12;
	static const int ENTRANCE = 13;
	static const int MASK = 14;		// covers joints and blocks light, no collision

	static string Name(int kind)
	{
		array<string> names = {"straight", "turn", "bend", "hump", "water", "slope", "upturn", "uturn", "ladder", "cap", "doorway", "doorcap", "room", "entrance", "mask"};
		if (kind < 0 || kind >= names.Count())
			return "?";

		return names[kind];
	}
}

class SP_TunnelSize
{
	static const int S = 0;		// standing
	static const int C = 1;		// crouching
	static const int P = 2;		// prone
	static const int D = 3;		// room doorframe

	static string Name(int size)
	{
		array<string> names = {"S", "C", "P", "D"};
		if (size < 0 || size >= names.Count())
			return "?";

		return names[size];
	}
}

class SP_TunnelRole
{
	static const int PATH = 0;		// corridor end, joins another corridor end of the same size
	static const int DOOR = 1;		// a room's doorframe, takes a doorway's room side
	static const int ROOMSIDE = 2;	// a doorway's (or blocked doorway's) side that goes into a room's doorframe
}

class SP_TunnelSocketDef
{
	vector m_vPos;	// in the piece's own space
	vector m_vDir;	// outward, horizontal, unit
	int m_iSize;
	int m_iRole;
	string m_sBone;
}

class SP_TunnelPieceDef
{
	ResourceName m_sPrefab;
	string m_sName;
	int m_iKind;
	int m_iSize;
	vector m_vMin;
	vector m_vMax;
	ref array<ref SP_TunnelSocketDef> m_aSockets = {};
	ref array<vector> m_aTops = {};		// the top of the piece (its roof and shell), measured every metre


	bool IsLarge()
	{
		return m_iKind == SP_TunnelKind.ROOM && (m_vMax[0] - m_vMin[0]) * (m_vMax[2] - m_vMin[2]) > 250;
	}
}

class SP_TunnelCatalog
{
	static const int KIT_EOH = 0;		// the EoH Modular Tunnel Pack
	static const int KIT_TT = 1;		// our own test kit (Prefabs/Tunnels/TT): one profile everywhere, rooms join tunnels directly

	int m_iKit;
	string m_sFile;
	string m_sRoot;
	protected static const vector PLACE_AT = "2048 700 2048";

	ref array<ref SP_TunnelPieceDef> m_aPieces = {};
	string m_sHash;

	//------------------------------------------------------------------------------------------------
	void SP_TunnelCatalog(int kit = 0)
	{
		m_iKit = kit;
		if (kit == KIT_TT)
		{
			m_sFile = "$profile:SP_TunnelCatalog_TT.txt";
			m_sRoot = "$Shashpul:Prefabs/Tunnels/TT";
		}
		else
		{
			m_sFile = "$profile:SP_TunnelCatalog.txt";
			m_sRoot = "$EoHModularTunnelPack:Prefabs";
		}
	}

	protected ref array<ResourceName> m_aFound = {};
	protected ref array<IEntity> m_aParts = {};
	protected BaseWorld m_World;

	//------------------------------------------------------------------------------------------------
	SP_TunnelPieceDef Find(string name)
	{
		foreach (SP_TunnelPieceDef piece : m_aPieces)
		{
			if (piece.m_sName == name)
				return piece;
		}

		return null;
	}

	//------------------------------------------------------------------------------------------------
	int IndexOfPrefab(ResourceName prefab)
	{
		// The file path, without the GUID, in small letters; nothing for an empty name (it used to match everything)
		string wanted = PathOf(prefab);
		if (wanted.IsEmpty())
			return -1;

		foreach (int index, SP_TunnelPieceDef piece : m_aPieces)
		{
			if (PathOf(piece.m_sPrefab) == wanted)
				return index;
		}

		return -1;
	}

	//------------------------------------------------------------------------------------------------
	static string PathOf(ResourceName prefab)
	{
		string path = prefab;
		int close = path.IndexOf("}");
		if (close >= 0)
			path = path.Substring(close + 1, path.Length() - close - 1);

		path.ToLower();
		return path;
	}

	//------------------------------------------------------------------------------------------------
	//! Loads the saved catalog, or builds it from the pack if there is none (or asked to)
	bool Get(WorldEditorAPI api, bool rebuild)
	{
		if (!rebuild && Load())
			return true;

		if (!api)
			return false;

		if (!Build(api))
			return false;

		Save();
		return Load();
	}

	//================================================================================================
	// Saving and loading
	//================================================================================================

	//------------------------------------------------------------------------------------------------
	protected string F(float value)
	{
		return value.ToString(-1, 4);
	}

	//------------------------------------------------------------------------------------------------
	protected string V(vector v)
	{
		return F(v[0]) + ";" + F(v[1]) + ";" + F(v[2]);
	}

	//------------------------------------------------------------------------------------------------
	void Save()
	{
		FileHandle file = FileIO.OpenFile(m_sFile, FileMode.WRITE);
		if (!file)
		{
			Print("SP_TunnelCatalog: can't write " + m_sFile, LogLevel.ERROR);
			return;
		}

		file.WriteLine("# EoH Modular Tunnel Pack catalog for the EoH Tunnel Generator. PIECE;name;prefab;kind;size;min;max  SOCK;pos;dir;size;role;bone");
		file.WriteLine("# Delete this file (or use Rebuild catalog) to measure the pack again. Edit with care: every layout depends on it.");
		foreach (SP_TunnelPieceDef piece : m_aPieces)
		{
			file.WriteLine(string.Format("PIECE;%1;%2;%3;%4;%5;%6", piece.m_sName, piece.m_sPrefab, piece.m_iKind, piece.m_iSize, V(piece.m_vMin), V(piece.m_vMax)));
			foreach (SP_TunnelSocketDef socket : piece.m_aSockets)
			{
				file.WriteLine(string.Format("SOCK;%1;%2;%3;%4;%5", V(socket.m_vPos), V(socket.m_vDir), socket.m_iSize, socket.m_iRole, socket.m_sBone));
			}

			foreach (vector roof : piece.m_aTops)
			{
				file.WriteLine("TOP;" + V(roof));
			}
		}

		file.Close();
		Print("SP_TunnelCatalog: saved " + m_aPieces.Count() + " pieces to " + m_sFile);
	}

	//------------------------------------------------------------------------------------------------
	//! A version number for the catalog: changes if any name, count or measurement in it changes
	protected int HashFields(int hash, array<string> fields)
	{
		foreach (string field : fields)
		{
			hash = hash * 31 + field.Length();
			hash = hash * 31 + Math.Round(field.ToFloat() * 1000);
		}

		return hash;
	}

	//------------------------------------------------------------------------------------------------
	bool Load()
	{
		if (!FileIO.FileExists(m_sFile))
			return false;

		FileHandle file = FileIO.OpenFile(m_sFile, FileMode.READ);
		if (!file)
			return false;

		m_aPieces.Clear();
		int hash = 17;
		string line;
		SP_TunnelPieceDef current;
		while (file.ReadLine(line) >= 0)
		{
			line.Trim();
			if (line.IsEmpty() || line.IndexOf("#") == 0)
				continue;

			array<string> f = {};
			line.Split(";", f, false);
			hash = HashFields(hash, f);
			if (f[0] == "PIECE" && f.Count() >= 11)
			{
				current = new SP_TunnelPieceDef();
				current.m_sName = f[1];
				current.m_sPrefab = f[2];
				current.m_iKind = f[3].ToInt();
				current.m_iSize = f[4].ToInt();
				current.m_vMin = Vector(f[5].ToFloat(), f[6].ToFloat(), f[7].ToFloat());
				current.m_vMax = Vector(f[8].ToFloat(), f[9].ToFloat(), f[10].ToFloat());
				m_aPieces.Insert(current);
			}
			else if (f[0] == "TOP" && f.Count() >= 4 && current)
			{
				current.m_aTops.Insert(Vector(f[1].ToFloat(), f[2].ToFloat(), f[3].ToFloat()));
			}
			else if (f[0] == "SOCK" && f.Count() >= 9 && current)
			{
				SP_TunnelSocketDef socket = new SP_TunnelSocketDef();
				socket.m_vPos = Vector(f[1].ToFloat(), f[2].ToFloat(), f[3].ToFloat());
				socket.m_vDir = Vector(f[4].ToFloat(), f[5].ToFloat(), f[6].ToFloat());
				socket.m_iSize = f[7].ToInt();
				socket.m_iRole = f[8].ToInt();
				if (f.Count() > 9)
					socket.m_sBone = f[9];

				current.m_aSockets.Insert(socket);
			}
		}

		file.Close();
		m_sHash = hash.ToString();
		Print(string.Format("SP_TunnelCatalog: loaded %1 pieces, hash %2", m_aPieces.Count(), m_sHash));
		return !m_aPieces.IsEmpty();
	}

	//================================================================================================
	// Building from the pack
	//================================================================================================

	//------------------------------------------------------------------------------------------------
	protected void OnFound(ResourceName resName, string filePath = "")
	{
		m_aFound.Insert(resName);
	}

	//------------------------------------------------------------------------------------------------
	protected string ShortName(ResourceName prefab)
	{
		string path = prefab;
		array<string> parts = {};
		path.Split("/", parts, true);
		string last = parts[parts.Count() - 1];
		last.Replace(".et", "");
		return last;
	}

	//------------------------------------------------------------------------------------------------
	//! What a prefab is, from where it is in the pack and its name. False: not used by the generator.
	protected bool Classify(ResourceName prefab, out int kind, out int size)
	{
		if (m_iKit == KIT_TT)
			return ClassifyTT(prefab, kind, size);

		string path = prefab;
		string name = ShortName(prefab);
		size = SP_TunnelSize.S;
		kind = -1;

		// No collision in the pack (players fall through), a duplicate, and something that's not a tunnel
		if (name == "C_Up_Turn_R" || name == "Room3_Split" || name == "S_Blocked_Path_Custom" || name == "Dirt_Bunker")
			return false;

		if (path.Contains("/Crouching/") || name.IndexOf("C_") == 0)
			size = SP_TunnelSize.C;
		else if (path.Contains("/Prone/") || name.IndexOf("P_") == 0)
			size = SP_TunnelSize.P;

		if (path.Contains("/Masks/"))
			kind = SP_TunnelKind.MASK;
		else if (path.Contains("/Rooms/") || name == "L_4x4m_2Room")
			kind = SP_TunnelKind.ROOM;
		else if (path.Contains("/Entrances/"))
		{
			kind = SP_TunnelKind.ENTRANCE;
			size = SP_TunnelSize.S;
			if (name == "Entrance_Floor_Hole" || name == "Entrance_Rocky")
				size = SP_TunnelSize.C;
			else if (name == "Entrance_Hill_Crawl")
				size = SP_TunnelSize.P;
		}
		else if (name == "Blocked_Doorway")
			kind = SP_TunnelKind.DOORCAP;
		else if (path.Contains("/Doorways/"))
			kind = SP_TunnelKind.DOORWAY;
		else if (name.Contains("Straight"))
			kind = SP_TunnelKind.STRAIGHT;
		else if (name.Contains("Left90") || name.Contains("Right90"))
			kind = SP_TunnelKind.TURN;
		else if (name.Contains("L_Bend") || name.Contains("R_Bend"))
			kind = SP_TunnelKind.BEND;
		else if (name.Contains("Up_Bend"))
			kind = SP_TunnelKind.HUMP;
		else if (name.Contains("Water_Trap"))
			kind = SP_TunnelKind.WATER;
		else if (name.Contains("Down_Slope"))
			kind = SP_TunnelKind.SLOPE;
		else if (name.Contains("Up_Turn"))
			kind = SP_TunnelKind.UPTURN;
		else if (name.Contains("U_Turn"))
			kind = SP_TunnelKind.UTURN;
		else if (name.Contains("Ladder"))
			kind = SP_TunnelKind.LADDER;
		else if (name.Contains("Blocked_Path"))
			kind = SP_TunnelKind.CAP;

		if (kind == SP_TunnelKind.ROOM || kind == SP_TunnelKind.DOORCAP)
			size = SP_TunnelSize.D;

		return kind >= 0;
	}

	//------------------------------------------------------------------------------------------------
	//! The test kit: one tunnel size (S); chambers and rooms have the tunnel's own openings
	protected bool ClassifyTT(ResourceName prefab, out int kind, out int size)
	{
		string name = ShortName(prefab);
		size = SP_TunnelSize.S;
		kind = -1;
		if (name.IndexOf("TT_") != 0)
			return false;

		if (name.Contains("Straight"))
			kind = SP_TunnelKind.STRAIGHT;
		else if (name.Contains("Turn"))
			kind = SP_TunnelKind.TURN;
		else if (name.Contains("Dogleg"))
			kind = SP_TunnelKind.BEND;
		else if (name.Contains("Slope"))
			kind = SP_TunnelKind.SLOPE;
		else if (name.Contains("End"))
			kind = SP_TunnelKind.CAP;
		else if (name.Contains("Junction") || name.Contains("Room"))
			kind = SP_TunnelKind.ROOM;
		else if (name.Contains("Entry"))
			kind = SP_TunnelKind.ENTRANCE;

		return kind >= 0;
	}

	//------------------------------------------------------------------------------------------------
	//! Memory points the models don't have, taken from their mirror image or from tracing their openings
	protected void MissingBones(string name, notnull array<string> names, notnull array<vector> positions)
	{
		if (name == "S_Up_Turn_R")
		{
			names.Insert("1");
			positions.Insert(Vector(-0.018, -0.241, 0));
			names.Insert("2");
			positions.Insert(Vector(5.511, 2.752, 7.618));
		}
		else if (name == "C_Straight_7.5m")
		{
			names.Insert("1");
			positions.Insert(Vector(-0.014, -0.051, -0.003));
			names.Insert("2");
			positions.Insert(Vector(-0.014, -0.051, 7.581));
		}
		else if (name == "Entrance_Rocky")
		{
			names.Insert("1");
			positions.Insert(Vector(-4.888, -1.647, -0.008));
		}
	}

	//------------------------------------------------------------------------------------------------
	protected void Collect(IEntity entity)
	{
		m_aParts.Insert(entity);
		IEntity child = entity.GetChildren();
		while (child)
		{
			Collect(child);
			child = child.GetSibling();
		}
	}

	//------------------------------------------------------------------------------------------------
	//! Nothing of the piece along this line
	protected bool Escapes(vector from, vector dir)
	{
		TraceParam trace = new TraceParam();
		trace.Start = from + dir * 0.05;
		trace.End = from + dir * 40;
		trace.Flags = TraceFlags.ENTS;
		trace.IncludeArray = m_aParts;
		return m_World.TraceMove(trace, null) >= 1;
	}

	//------------------------------------------------------------------------------------------------
	//! How far a point is from the side of the box that faces this way (an axis direction)
	protected float FaceGap(vector local, vector dir, vector low, vector high)
	{
		if (dir[0] > 0.5)
			return Math.AbsFloat(high[0] - local[0]);

		if (dir[0] < -0.5)
			return Math.AbsFloat(local[0] - low[0]);

		if (dir[2] > 0.5)
			return Math.AbsFloat(high[2] - local[2]);

		return Math.AbsFloat(local[2] - low[2]);
	}

	//------------------------------------------------------------------------------------------------
	//! The top of the piece every metre across its box, by tracing down onto its collision: what the earth over it is
	//! measured to (a slope's low end is lower, a turn's empty corner has nothing)
	protected void MeasureTops(SP_TunnelPieceDef piece)
	{
		piece.m_aTops.Clear();
		vector low = piece.m_vMin;
		vector high = piece.m_vMax;
		int countX = Math.Max(2, Math.Ceil(high[0] - low[0]) + 1);
		int countZ = Math.Max(2, Math.Ceil(high[2] - low[2]) + 1);
		for (int ix = 0; ix < countX; ix++)
		{
			for (int iz = 0; iz < countZ; iz++)
			{
				float x = low[0] + (high[0] - low[0]) * ix / (countX - 1);
				float z = low[2] + (high[2] - low[2]) * iz / (countZ - 1);
				TraceParam down = new TraceParam();
				down.Start = PLACE_AT + Vector(x, high[1] + 1, z);
				down.End = PLACE_AT + Vector(x, low[1] - 1, z);
				down.Flags = TraceFlags.ENTS;
				down.IncludeArray = m_aParts;
				float hit = m_World.TraceMove(down, null);
				if (hit >= 1)
					continue;

				float y = down.Start[1] + (down.End[1] - down.Start[1]) * hit - PLACE_AT[1];
				piece.m_aTops.Insert(Vector(x, y, z));
			}
		}
	}

	//------------------------------------------------------------------------------------------------
	//! Which way a socket faces out of its piece: of the four horizontal directions, the ones where nothing of the piece
	//! is in the way, and of those the one where the socket is closest to the edge of the piece
	protected vector OutwardOf(vector local, vector low, vector high)
	{
		array<vector> dirs = {"1 0 0", "-1 0 0", "0 0 1", "0 0 -1"};
		vector best = dirs[0];
		float bestGap = 100000;
		bool bestEscapes = false;
		foreach (vector dir : dirs)
		{
			float edge = high[0];
			float at = local[0];
			if (dir[0] < 0)
			{
				edge = -low[0];
				at = -local[0];
			}
			else if (dir[2] > 0)
			{
				edge = high[2];
				at = local[2];
			}
			else if (dir[2] < 0)
			{
				edge = -low[2];
				at = -local[2];
			}

			float gap = Math.AbsFloat(edge - at);
			bool escapes = Escapes(PLACE_AT + local, dir);
			if ((escapes && !bestEscapes) || (escapes == bestEscapes && gap < bestGap))
			{
				best = dir;
				bestGap = gap;
				bestEscapes = escapes;
			}
		}

		return best;
	}

	//------------------------------------------------------------------------------------------------
	protected bool Build(WorldEditorAPI api)
	{
		m_World = api.GetWorld();
		m_aFound.Clear();
		Workbench.SearchResources(OnFound, {"et"}, null, m_sRoot, true);
		if (m_aFound.IsEmpty())
		{
			Print("SP_TunnelCatalog: no prefabs found under " + m_sRoot, LogLevel.ERROR);
			return false;
		}

		// The same order every time, whatever order the files are found in
		array<string> sorted = {};
		foreach (ResourceName found : m_aFound)
		{
			sorted.Insert(found);
		}

		sorted.Sort();
		m_aPieces.Clear();
		foreach (string prefabText : sorted)
		{
			ResourceName prefab = prefabText;
			int kind;
			int size;
			if (!Classify(prefab, kind, size))
				continue;

			SP_TunnelPieceDef piece = BuildPiece(api, prefab, kind, size);
			if (piece)
				m_aPieces.Insert(piece);
		}

		Print(string.Format("SP_TunnelCatalog: built %1 pieces from %2 prefabs", m_aPieces.Count(), sorted.Count()));
		return !m_aPieces.IsEmpty();
	}

	//------------------------------------------------------------------------------------------------
	protected SP_TunnelPieceDef BuildPiece(WorldEditorAPI api, ResourceName prefab, int kind, int size)
	{
		api.BeginEntityAction("SP tunnel catalog");
		IEntitySource src = api.CreateEntity(prefab, "", api.GetCurrentEntityLayerId(), null, PLACE_AT, vector.Zero);
		api.EndEntityAction();
		if (!src)
		{
			Print("SP_TunnelCatalog: can't create " + prefab, LogLevel.WARNING);
			return null;
		}

		SP_TunnelPieceDef piece = new SP_TunnelPieceDef();
		piece.m_sPrefab = prefab;
		piece.m_sName = ShortName(prefab);
		piece.m_iKind = kind;
		piece.m_iSize = size;
		IEntity entity = api.SourceToEntity(src);
		if (entity)
		{
			m_aParts.Clear();
			Collect(entity);
			vector low;
			vector high;
			entity.GetWorldBounds(low, high);
			foreach (IEntity part : m_aParts)
			{
				vector partLow;
				vector partHigh;
				part.GetWorldBounds(partLow, partHigh);
				for (int axis = 0; axis < 3; axis++)
				{
					low[axis] = Math.Min(low[axis], partLow[axis]);
					high[axis] = Math.Max(high[axis], partHigh[axis]);
				}
			}

			piece.m_vMin = low - PLACE_AT;
			piece.m_vMax = high - PLACE_AT;

			// Memory points: bones of the model (not the root)
			array<string> boneNames = {};
			array<vector> bonePositions = {};
			array<vector> boneForwards = {};
			Animation anim = entity.GetAnimation();
			if (anim)
			{
				array<string> names = {};
				anim.GetBoneNames(names);
				foreach (string bone : names)
				{
					if (bone == "Scene_Root")
						continue;

					vector boneMat[4];
					if (!anim.GetBoneMatrix(anim.GetBoneIndex(bone), boneMat))
						continue;

					boneNames.Insert(bone);
					bonePositions.Insert(boneMat[3]);
					boneForwards.Insert(boneMat[2]);
				}
			}

			if (boneNames.IsEmpty())
			{
				MissingBones(piece.m_sName, boneNames, bonePositions);
				foreach (vector unused : bonePositions)
				{
					boneForwards.Insert("0 0 1");
				}
			}

			AddSockets(piece, boneNames, bonePositions, boneForwards);
			MeasureTops(piece);
		}

		api.BeginEntityAction("SP tunnel catalog delete");
		api.DeleteEntity(src);
		api.EndEntityAction();
		if (piece.m_aSockets.IsEmpty() && kind != SP_TunnelKind.MASK)
		{
			Print("SP_TunnelCatalog: no sockets on " + prefab + ", left out", LogLevel.WARNING);
			return null;
		}

		return piece;
	}

	//------------------------------------------------------------------------------------------------
	protected void AddSockets(SP_TunnelPieceDef piece, array<string> names, array<vector> positions, array<vector> forwards)
	{
		if (piece.m_iKind == SP_TunnelKind.MASK)
			return;

		foreach (int b, string bone : names)
		{
			vector pos = positions[b];
			vector forward = forwards[b];
			forward[1] = 0;
			bool defaultFacing = forward.Length() < 0.5 || (Math.AbsFloat(forward[0]) < 0.02 && forward[2] > 0.98);

			SP_TunnelSocketDef socket = new SP_TunnelSocketDef();
			socket.m_vPos = pos;
			socket.m_sBone = bone;
			socket.m_iSize = piece.m_iSize;
			socket.m_iRole = SP_TunnelRole.PATH;

			// Rooms whose memory points really face somewhere face into the room: out is the other way. One set at an angle
			// (Room1, Room5, Room11) is taken as it is. One along an axis is checked against the room's shape, as some are
			// turned wrong in the model (Room10_A's doorframe '1' sits on the -Z wall but points along X): the way that
			// puts the doorframe against its wall wins.
			socket.m_vDir = OutwardOf(pos, piece.m_vMin, piece.m_vMax);
			if (m_iKit != KIT_TT && piece.m_iKind == SP_TunnelKind.ROOM && !defaultFacing)
			{
				forward.Normalize();
				vector fromBone = -forward;
				bool alongAxis = Math.AbsFloat(fromBone[0]) > 0.98 || Math.AbsFloat(fromBone[2]) > 0.98;
				if (!alongAxis || FaceGap(pos, fromBone, piece.m_vMin, piece.m_vMax) <= FaceGap(pos, socket.m_vDir, piece.m_vMin, piece.m_vMax) + 0.05)
					socket.m_vDir = fromBone;
				else
					Print(string.Format("SP_TunnelCatalog: %1 doorframe '%2' points %3 in the model but sits on the wall facing %4: using that", piece.m_sName, bone, fromBone, socket.m_vDir), LogLevel.WARNING);
			}

			if (m_iKit != KIT_TT && piece.m_iKind == SP_TunnelKind.ROOM)
			{
				socket.m_iSize = SP_TunnelSize.D;
				socket.m_iRole = SP_TunnelRole.DOOR;
			}

			piece.m_aSockets.Insert(socket);

			// A doorway's pivot goes into the room's doorframe, its "Pathway" memory point takes the corridor
			if (piece.m_iKind == SP_TunnelKind.DOORWAY || piece.m_iKind == SP_TunnelKind.DOORCAP)
			{
				SP_TunnelSocketDef roomSide = new SP_TunnelSocketDef();
				roomSide.m_vPos = vector.Zero;
				roomSide.m_vDir = -socket.m_vDir;
				roomSide.m_iSize = SP_TunnelSize.D;
				roomSide.m_iRole = SP_TunnelRole.ROOMSIDE;
				roomSide.m_sBone = "Scene_Root";
				if (piece.m_iKind == SP_TunnelKind.DOORCAP)
				{
					// A blocked doorway only closes a doorframe
					piece.m_aSockets.Clear();
				}

				piece.m_aSockets.Insert(roomSide);
				break;
			}
		}
	}
}
#endif
